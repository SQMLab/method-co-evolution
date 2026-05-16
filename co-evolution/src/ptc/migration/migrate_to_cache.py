"""Move a published per-project CSV back into its hidden scan cache.

Use case: ``mhc method-scan`` (and similar) maintain a hidden cache at
``<data>/.<name>/<project>.csv`` that carries two extra columns, ``_flag``
and ``_error``, used to track ``__scan_marker__`` / ``__error_marker__``
rows. The clean published file at ``<data>/<name>/<project>.csv`` drops
those columns.

If the cache is lost (or you want successful rows from a previous run to
count as "already done" by the next scan), this migration:

  1. Reads ``<data>/<name>/<project>.csv``.
  2. Adds any columns that exist in the cache but not in the published
     file (``_flag`` and ``_error`` in practice), as empty strings.
  3. Reorders columns to match the cache schema.
  4. Appends the rows to ``<data>/.<name>/<project>.csv`` (creates it if
     missing).
  5. Optionally drops exact duplicates (``--dedupe``).
  6. Deletes the published file so the next scan rebuilds it cleanly.

The cache's completion check is ``_flag != __error_marker__`` and ``file``
non-empty, so the migrated rows are treated as completed and the scanner
only retries actual ``__error_marker__`` files on the next run.

Run via::

    python -m ptc.migration.migrate_to_cache \\
        --data-directory workspace/data \\
        --name method \\
        --project-index "47"
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from mhc.util import parse_project_index


@dataclass(frozen=True)
class MigrationResult:
    project: str
    published_rows: int
    cache_rows_before: int
    cache_rows_after: int
    added_columns: tuple[str, ...]
    duplicates_dropped: int
    published_file_deleted: bool
    dry_run: bool


def _load_repository_projects(data_directory: Path) -> list[str]:
    repository_file = data_directory / "repository" / "repository.csv"
    if not repository_file.exists():
        raise FileNotFoundError(f"repository index not found: {repository_file}")
    repo_df = pd.read_csv(repository_file, keep_default_na=False, na_filter=False)
    if "project" not in repo_df.columns:
        raise ValueError(f"repository index is missing 'project' column: {repository_file}")
    return repo_df["project"].dropna().astype(str).tolist()


def _read_csv_as_strings(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False, na_filter=False)


def _align_to_cache_schema(
    published_df: pd.DataFrame,
    cache_columns: list[str],
) -> tuple[pd.DataFrame, list[str]]:
    """Return ``published_df`` with cache-only columns added as ``""``,
    columns reordered to match ``cache_columns``. Columns present in
    published but not in cache are preserved at the end (shouldn't happen
    in practice, but keeps the script lossless)."""

    added: list[str] = []
    aligned = published_df.copy()
    for column in cache_columns:
        if column not in aligned.columns:
            aligned[column] = ""
            added.append(column)

    extra = [c for c in aligned.columns if c not in cache_columns]
    return aligned[cache_columns + extra], added


def migrate_project(
    *,
    project: str,
    data_directory: Path,
    name: str,
    dedupe: bool,
    dry_run: bool,
) -> MigrationResult | None:
    published_file = data_directory / name / f"{project}.csv"
    cache_file = data_directory / f".{name}" / f"{project}.csv"

    if not published_file.exists():
        print(f"  {project}: skipped, published file does not exist: {published_file}")
        return None

    published_df = _read_csv_as_strings(published_file)
    cache_exists = cache_file.exists()

    if cache_exists:
        cache_df = _read_csv_as_strings(cache_file)
        cache_columns = list(cache_df.columns)
    else:
        # Cache doesn't exist — start from the published schema and
        # ensure the two scanner flag columns are present so the next
        # scan can read it back.
        cache_df = pd.DataFrame(columns=list(published_df.columns))
        cache_columns = list(published_df.columns)
        for required in ("_flag", "_error"):
            if required not in cache_columns:
                cache_columns.append(required)

    aligned_df, added_columns = _align_to_cache_schema(published_df, cache_columns)

    if cache_exists:
        # Realign cache_df too in case the published file has columns
        # the cache lacks (rare, but keeps concat lossless).
        for column in aligned_df.columns:
            if column not in cache_df.columns:
                cache_df[column] = ""
        cache_df = cache_df[aligned_df.columns]

    cache_rows_before = len(cache_df)
    merged = pd.concat([cache_df, aligned_df], ignore_index=True)

    duplicates_dropped = 0
    if dedupe:
        before = len(merged)
        # keep='first' preserves cache rows (which come first), so
        # re-running the migration is a no-op rather than a duplicator.
        merged = merged.drop_duplicates(keep="first").reset_index(drop=True)
        duplicates_dropped = before - len(merged)

    cache_rows_after = len(merged)

    if not dry_run:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_file = cache_file.with_suffix(f"{cache_file.suffix}.tmp")
        merged.to_csv(tmp_file, index=False)
        os.replace(tmp_file, cache_file)
        published_file.unlink()
        published_file_deleted = True
    else:
        published_file_deleted = False

    return MigrationResult(
        project=project,
        published_rows=len(published_df),
        cache_rows_before=cache_rows_before,
        cache_rows_after=cache_rows_after,
        added_columns=tuple(added_columns),
        duplicates_dropped=duplicates_dropped,
        published_file_deleted=published_file_deleted,
        dry_run=dry_run,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Move rows from <data>/<name>/<project>.csv back into the "
            "hidden scan cache at <data>/.<name>/<project>.csv so the next "
            "scan only retries files marked as __error_marker__."
        ),
    )
    parser.add_argument(
        "--data-directory",
        required=True,
        type=Path,
        help="Data directory containing <name>/, .<name>/, and repository/repository.csv.",
    )
    parser.add_argument(
        "--name",
        required=True,
        help="Cache name to migrate, e.g. 'method' or 'callgraph'. "
             "Reads from <data>/<name>/ and writes to <data>/.<name>/.",
    )
    parser.add_argument(
        "--project-index",
        required=True,
        help="Python-style project index or slice from <data>/repository/repository.csv "
             "(e.g. '47', '10:20', ':10', ':').",
    )
    parser.add_argument(
        "--dedupe",
        action="store_true",
        help="Drop exact-duplicate rows after concat (keep='first' favors existing cache rows).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without writing the cache or deleting the published file.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    data_directory: Path = args.data_directory.expanduser().resolve()
    if not data_directory.is_dir():
        parser.error(f"--data-directory does not exist: {data_directory}")

    name: str = args.name.strip()
    if not name:
        parser.error("--name must be non-empty")

    published_dir = data_directory / name
    cache_dir = data_directory / f".{name}"
    if not published_dir.is_dir() and not cache_dir.is_dir():
        parser.error(
            f"neither {published_dir} nor {cache_dir} exists; nothing to migrate"
        )

    try:
        projects = parse_project_index(
            args.project_index,
            _load_repository_projects(data_directory),
        )
    except ValueError as exc:
        parser.error(str(exc))

    if not projects:
        print("No projects selected.")
        return 0

    print(f"Data directory: {data_directory}")
    print(f"Name: {name}")
    print(f"Published dir: {published_dir}")
    print(f"Cache dir: {cache_dir}")
    print(f"Selected projects: {len(projects)}")
    if args.dedupe:
        print("Dedupe: enabled (drop_duplicates keep=first)")
    if args.dry_run:
        print("Dry-run: no files will be modified")
    print()

    results: list[MigrationResult] = []
    for project in projects:
        result = migrate_project(
            project=project,
            data_directory=data_directory,
            name=name,
            dedupe=args.dedupe,
            dry_run=args.dry_run,
        )
        if result is None:
            continue
        results.append(result)
        suffix = " (dry-run)" if result.dry_run else ""
        added = f" added cols=[{', '.join(result.added_columns)}]" if result.added_columns else ""
        dropped = f" dedupe_dropped={result.duplicates_dropped}" if result.duplicates_dropped else ""
        deleted = " published-deleted" if result.published_file_deleted else ""
        print(
            f"  {result.project}: published={result.published_rows} "
            f"cache_before={result.cache_rows_before} "
            f"cache_after={result.cache_rows_after}"
            f"{added}{dropped}{deleted}{suffix}"
        )

    print(
        f"\nTotal: {len(results)} project(s), "
        f"published_rows={sum(r.published_rows for r in results)}, "
        f"cache_rows_added={sum(r.cache_rows_after - r.cache_rows_before for r in results)}, "
        f"dedupe_dropped={sum(r.duplicates_dropped for r in results)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

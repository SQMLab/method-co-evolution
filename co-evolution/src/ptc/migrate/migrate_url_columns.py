#!/usr/bin/env python3
"""Remove stale ``.git`` repository suffixes from generated blob URLs.

This migration scans the xunit experiment CSV artifacts and rewrites URL-like
columns so values such as::

    https://github.com/owner/repo.git/blob/<commit>/path/File.java#L1

become::

    https://github.com/owner/repo/blob/<commit>/path/File.java#L1

Only columns named ``url`` or ending in ``_url`` are migrated.
"""

from __future__ import annotations

import argparse
import csv
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


TARGETS = ("callgraph", "class", "fanin", "method", "method-code")
OLD_FRAGMENT = ".git/blob"
NEW_FRAGMENT = "/blob"


@dataclass(frozen=True)
class MigrationResult:
    file: Path
    target: str
    rows: int
    changed_rows: int
    changed_cells: int
    written: bool


def _raise_csv_field_limit() -> None:
    """Allow very large CSV cells, especially method-code ``code`` cells."""

    limit = sys.maxsize
    while True:
        try:
            csv.field_size_limit(limit)
            return
        except OverflowError:
            limit //= 10


def is_url_column(column_name: str) -> bool:
    normalized = column_name.strip()
    return normalized == "url" or normalized.endswith("_url")


def normalize_url(value: str) -> str:
    return value.replace(OLD_FRAGMENT, NEW_FRAGMENT)


def migrate_file(
    csv_file: Path,
    target: str,
    *,
    dry_run: bool = False,
    backup: bool = False,
) -> MigrationResult:
    _raise_csv_field_limit()

    changed_rows = 0
    changed_cells = 0
    row_count = 0
    tmp_path: Path | None = None

    with csv_file.open(newline="", encoding="utf-8") as source:
        reader = csv.reader(source)
        try:
            header = next(reader)
        except StopIteration:
            return MigrationResult(csv_file, target, 0, 0, 0, False)

        url_indexes = [index for index, column in enumerate(header) if is_url_column(column)]

        if not dry_run:
            tmp_handle = tempfile.NamedTemporaryFile(
                "w",
                newline="",
                encoding="utf-8",
                dir=csv_file.parent,
                prefix=f".{csv_file.name}.",
                suffix=".tmp",
                delete=False,
            )
            tmp_path = Path(tmp_handle.name)
        else:
            tmp_handle = None

        try:
            writer = csv.writer(tmp_handle) if tmp_handle is not None else None
            if writer is not None:
                writer.writerow(header)

            for row in reader:
                row_count += 1
                row_changed = False

                for index in url_indexes:
                    if index >= len(row):
                        continue
                    original_value = row[index]
                    normalized_value = normalize_url(original_value)
                    if normalized_value != original_value:
                        row[index] = normalized_value
                        row_changed = True
                        changed_cells += 1

                if row_changed:
                    changed_rows += 1

                if writer is not None:
                    writer.writerow(row)
        finally:
            if tmp_handle is not None:
                tmp_handle.close()

    should_write = changed_cells > 0 and not dry_run
    if should_write:
        if backup:
            backup_file = csv_file.with_name(f"bk_{csv_file.name}")
            shutil.copy2(csv_file, backup_file)
        os.replace(tmp_path, csv_file)
    elif tmp_path is not None:
        tmp_path.unlink(missing_ok=True)

    return MigrationResult(
        file=csv_file,
        target=target,
        rows=row_count,
        changed_rows=changed_rows,
        changed_cells=changed_cells,
        written=should_write,
    )


def collect_csv_files(
    data_directory: Path,
    targets: Iterable[str],
    projects: set[str] | None,
) -> list[tuple[str, Path]]:
    files: list[tuple[str, Path]] = []
    for target in targets:
        target_dir = data_directory / target
        if projects:
            files.extend((target, target_dir / f"{project}.csv") for project in sorted(projects))
        elif target_dir.exists():
            files.extend((target, path) for path in sorted(target_dir.glob("*.csv")))
    return files


def parse_projects(values: list[str] | None) -> set[str] | None:
    if not values:
        return None
    projects: set[str] = set()
    for value in values:
        projects.update(part.strip() for part in value.split(",") if part.strip())
    return projects or None


def parse_targets(value: str) -> list[str]:
    targets = [part.strip() for part in value.split(",") if part.strip()]
    unknown = sorted(set(targets) - set(TARGETS))
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown target(s): {', '.join(unknown)}")
    return targets


def run_migration(
    data_directory: Path,
    targets: list[str],
    *,
    projects: set[str] | None = None,
    dry_run: bool = False,
    backup: bool = False,
) -> list[MigrationResult]:
    results: list[MigrationResult] = []
    for target, csv_file in collect_csv_files(data_directory, targets, projects):
        if not csv_file.exists():
            print(f"{csv_file}: skipped, file does not exist")
            continue

        result = migrate_file(csv_file, target, dry_run=dry_run, backup=backup)
        results.append(result)
        action = "dry run" if dry_run else "written" if result.written else "already clean"
        print(
            f"{csv_file}: {result.rows} row(s), "
            f"{result.changed_rows} row(s) changed, {result.changed_cells} cell(s) changed; "
            f"{action}"
        )
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Remove '.git' before '/blob' in URL columns for xunit experiment "
            "callgraph, class, fanin, method, and method-code CSV artifacts."
        ),
    )
    parser.add_argument(
        "--data-directory",
        type=Path,
        default=Path("workspace/experiment/xunit"),
        help="Experiment directory containing callgraph, class, fanin, method, and method-code subdirectories.",
    )
    parser.add_argument(
        "--target",
        default=",".join(TARGETS),
        type=parse_targets,
        help=f"Comma-separated targets to migrate. Supported: {','.join(TARGETS)}.",
    )
    parser.add_argument(
        "--project",
        action="append",
        help="Project name to migrate. May be repeated or comma-separated. Defaults to all CSVs for selected targets.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing CSVs.")
    parser.add_argument("--backup", action="store_true", help="Create bk_<project>.csv before rewriting a CSV.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    run_migration(
        args.data_directory.expanduser(),
        args.target,
        projects=parse_projects(args.project),
        dry_run=args.dry_run,
        backup=args.backup,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

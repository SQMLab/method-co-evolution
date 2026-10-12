import json
import logging
import math
import os
import re
import tarfile
import warnings
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import mhc.util as util
from mhc.command_util import (
    build_experiment_parser,
    filter_artifact_dataframe,
    resolve_experiment_filters,
    resolve_experiment_paths,
    select_named_items,
    select_revision_columns,
)
from ptc.constants import MethodChangeType
from ptc.util.helper import extract_change_count, initial_method_line_count
from ptc.generator.run_stats import GenerationStats, should_generate, unlink_stale_output

CHANGE_COLUMNS = [
    "ch_all",
    "ch_diff",
    *[f"ch_{change_type.name.lower()}" for change_type in MethodChangeType],
]
INTEGER_OUTPUT_COLUMNS = {"loc_init", "age"}


def parse_commit_date(value: object) -> datetime | None:
    if value is None or pd.isna(value):
        return None

    normalized = str(value).replace("\u202f", " ").replace("\xa0", " ").strip()
    normalized = re.sub(r"\b00:(\d{2})\s*AM\b", r"12:\1 AM", normalized, flags=re.IGNORECASE)
    match = re.search(r"(\d{1,2}):(\d{2})\s*([AP]M)$", normalized, flags=re.IGNORECASE)
    if match and int(match.group(1)) > 12:
        normalized = re.sub(r"\s*([AP]M)$", "", normalized, flags=re.IGNORECASE)

    for pattern in (
        "%d/%m/%y %I:%M %p",
        "%d/%m/%y %H:%M",
        "%d/%m/%Y %I:%M %p",
        "%d/%m/%Y %H:%M",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
    ):
        try:
            parsed = datetime.strptime(normalized, pattern)
            return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def introduction_detail(history_json: dict) -> dict | None:
    details = history_json.get("changeHistoryDetails", {})
    if isinstance(details, dict):
        candidates = details.values()
    elif isinstance(details, list):
        candidates = details
    else:
        return None

    return next(
        (
            detail
            for detail in candidates
            if isinstance(detail, dict) and str(detail.get("type", "")) == "Yintroduced"
        ),
        None,
    )


def method_age_days(history_json: dict, snapshot_date: datetime | None) -> int | None:
    detail = introduction_detail(history_json)
    introduction_date = parse_commit_date(detail.get("commitDate")) if detail else None
    if introduction_date is None or snapshot_date is None:
        return None

    elapsed_seconds = (snapshot_date - introduction_date).total_seconds()
    if elapsed_seconds < 0:
        return None
    if elapsed_seconds == 0:
        return 0
    return math.ceil(elapsed_seconds / 86_400)


def normalize_integer_output_columns(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    for column in normalized.columns:
        if column.startswith("ch_") or column in INTEGER_OUTPUT_COLUMNS:
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce").astype("Int64")
    return normalized


def iter_tool_history_directories(history_root: Path) -> list[Path]:
    if not history_root.exists():
        return []

    return sorted(path for path in history_root.iterdir() if path.is_dir())


def move_tool_after_project(df: pd.DataFrame) -> pd.DataFrame:
    cols = list(df.columns)
    if "tool" in cols and "project" in cols:
        cols.remove("tool")
        project_idx = cols.index("project")
        cols.insert(project_idx + 1, "tool")
    return df[cols]


def order_change_columns(df: pd.DataFrame) -> pd.DataFrame:
    metadata_columns = [
        column for column in df.columns
        if not column.startswith("ch_") and column not in {"loc_init", "age"}
    ]
    change_columns = select_revision_columns(df.columns, preferred_order=CHANGE_COLUMNS)
    trailing_columns = [column for column in ("loc_init", "age") if column in df.columns]
    return df[metadata_columns + change_columns + trailing_columns]


def build_parser():
    return build_experiment_parser(
        "Generate per-method revision counts from method history archives.",
        include_strategies=False,
        include_replace=True,
        projects_help="Comma-separated project names to process.",
        tools_help="Comma-separated history tool names to process.",
    )


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    stats = GenerationStats("artifact_revision")
    experiment_directory = resolve_experiment_paths(
        getattr(args, "workspace_directory", None),
        args.experiment_name,
    ).experiment_directory
    repository_df = pd.read_csv(experiment_directory / "project.csv")
    repository_name_map = {row["project"]: row for row in repository_df.to_dict(orient="records")}
    selected_tools, selected_projects, _ = resolve_experiment_filters(
        tools=args.tools,
        projects=args.projects,
    )
    projects = select_named_items(repository_df["project"].tolist(), selected_projects, item_label="project")
    selected_project_set = set(projects)
    history_root = experiment_directory / "method-history-gz"

    tool_directory_map = {path.name: path for path in iter_tool_history_directories(history_root)}
    tool_names = select_named_items(
        list(tool_directory_map),
        selected_tools,
        item_label="tool",
    )
    for tool_name in tool_names:
        tool_directory = tool_directory_map[tool_name]
        tool_name = tool_directory.name
        processed_count = 0
        skipped_count = 0
        empty_history_count = 0
        invalid_history_count = 0

        for zip_file in tool_directory.rglob("*.tar.gz"):
            method_history_list = []
            repository_name = zip_file.name[:-len(".tar.gz")]
            repository_change_history_file = experiment_directory / "method-history" / tool_name / f"{repository_name}.csv"
            if repository_name not in repository_name_map:
                print(f"Skipping: {repository_name} [{tool_name}] (not in project.csv)")
                unlink_stale_output(
                    repository_change_history_file,
                    reason=f"Skipping: {repository_name} [{tool_name}] (not in project.csv)",
                    stats=stats,
                )
                skipped_count += 1
                continue
            if repository_name not in selected_project_set:
                continue
            if repository_name in repository_name_map:
                method_file = util.format_method_list_file(str(experiment_directory), repository_name)
                if not os.path.exists(method_file):
                    print(f"Skipping: {repository_name} [{tool_name}] (missing method file)")
                    unlink_stale_output(
                        repository_change_history_file,
                        reason=f"Skipping: {repository_name} [{tool_name}] (missing method file)",
                        stats=stats,
                    )
                    warnings.warn(f"Missing method history file for {tool_name} {repository_name}")
                    skipped_count += 1
                    continue
                if not should_generate(
                    repository_change_history_file,
                    replace=args.replace,
                    label=f"{repository_name} [{tool_name}]",
                    stats=stats,
                ):
                    skipped_count += 1
                    continue

                print(f"Processing: {repository_name} [{tool_name}]")
                repository_url = repository_name_map[repository_name]["url"]
                repository_hash = repository_name_map[repository_name]["updated_hash"]
                snapshot_date = parse_commit_date(repository_name_map[repository_name].get("updated_at"))
                missing_age_count = 0
                try:
                    tar_cm = tarfile.open(zip_file, "r:gz")
                except Exception:
                    logging.warning("Skipping unreadable archive: %s", zip_file)
                    skipped_count += 1
                    continue
                with tar_cm as tar:
                    try:
                        members = tar.getmembers()
                    except EOFError:
                        logging.warning("Truncated archive (EOFError), skipping: %s", zip_file)
                        skipped_count += 1
                        continue
                    for member in members:
                        if member.isfile() and member.name.endswith(".json"):
                            _, base_file = member.name.split("/", maxsplit=1)
                            file_content = tar.extractfile(member)
                            if file_content is not None:
                                try:
                                    raw_history = file_content.read()
                                    if not raw_history.strip():
                                        empty_history_count += 1
                                        continue
                                    history_json = json.loads(raw_history)
                                except json.JSONDecodeError:
                                    invalid_history_count += 1
                                    continue
                                except Exception:
                                    logging.exception(
                                        "Unexpected error loading history json for %s %s",
                                        tool_name,
                                        member,
                                    )
                                    continue
                                change_history = extract_change_count(history_json)

                                method_url = util.convert_method_file_to_method_url(
                                    repository_url, repository_hash, base_file
                                )
                                method_history = {
                                    "url": method_url,
                                    "tool": tool_name,
                                    "method_file": base_file,
                                    "loc_init": initial_method_line_count(history_json),
                                    "age": method_age_days(history_json, snapshot_date),
                                }
                                if method_history["age"] is None:
                                    missing_age_count += 1
                                method_history.update(change_history)
                                method_history_list.append(method_history)
                method_list_df = pd.read_csv(
                    method_file,
                    keep_default_na=False,
                    na_filter=False,
                    low_memory=False,
                )
                os.makedirs(repository_change_history_file.parent, exist_ok=True)
                history_df = pd.DataFrame(method_history_list)
                if "url" not in history_df.columns:
                    history_df = pd.DataFrame(columns=["url"])
                repository_change_history_df = pd.merge(
                    method_list_df,
                    history_df,
                    on="url",
                    how="inner",
                )
                output_df = normalize_integer_output_columns(
                    order_change_columns(
                        move_tool_after_project(filter_artifact_dataframe(repository_change_history_df))
                    )
                )
                if output_df.empty:
                    stats.record_empty_output()
                output_df.to_csv(
                    repository_change_history_file,
                    index=False,
                )
                stats.record_write(len(output_df))
                processed_count += 1
                if missing_age_count:
                    logging.warning(
                        "Missing age for %d method histories in %s [%s]",
                        missing_age_count,
                        repository_name,
                        tool_name,
                    )
        print(
            f"generate_change summary [{tool_name}]: "
            f"processed={processed_count}, skipped={skipped_count}, "
            f"empty_history={empty_history_count}, invalid_history={invalid_history_count}"
        )
    stats.print_summary()


if __name__ == "__main__":
    main()

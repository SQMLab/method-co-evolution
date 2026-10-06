from __future__ import annotations

import math
import os
import warnings
from pathlib import Path

import pandas as pd
from scipy.stats import kendalltau, pearsonr, spearmanr

import mhc.util as util
from mhc.command_util import (
    build_experiment_parser,
    list_csv_files,
    resolve_experiment_filters,
    resolve_experiment_paths,
    select_named_items,
)
from ptc.generator.run_stats import GenerationStats, should_generate
from ptc.util.helper import (
    TEST_REVISION_METHOD_KIND,
    filter_revision_method_base_population,
)

OUTPUT_FILE_NAME = "artifact-revision-loc-correlation.csv"
OUTPUT_COLUMNS = [
    "tool",
    "method_kind",
    "change",
    "methods",
    "loc_init_min",
    "loc_init_median",
    "loc_init_max",
    "revision_min",
    "revision_median",
    "revision_max",
    "correlation_algorithm",
    "correlation",
    "p_value",
]
CHANGE_COLUMN = "ch_diff"
LOC_COLUMN = "loc_init"


def build_parser():
    return build_experiment_parser(
        "Correlate initial test-method LOC with total method revisions.",
        include_strategies=False,
        include_replace=True,
        projects_help="Comma-separated project names to include in the pooled correlation.",
        tools_help="Comma-separated history tool names to process.",
    )


def pooled_test_methods(df: pd.DataFrame) -> pd.DataFrame:
    required = {"method_kind", LOC_COLUMN, CHANGE_COLUMN}
    if not required.issubset(df.columns):
        return pd.DataFrame(columns=[LOC_COLUMN, CHANGE_COLUMN])

    methods = df[df["method_kind"] == TEST_REVISION_METHOD_KIND][
        [LOC_COLUMN, CHANGE_COLUMN]
    ].copy()
    methods[LOC_COLUMN] = pd.to_numeric(methods[LOC_COLUMN], errors="coerce")
    methods[CHANGE_COLUMN] = pd.to_numeric(methods[CHANGE_COLUMN], errors="coerce")
    return methods.dropna(subset=[LOC_COLUMN, CHANGE_COLUMN])


def correlation_rows(methods: pd.DataFrame, *, tool: str) -> list[dict]:
    valid = pooled_test_methods(methods)
    if valid.empty:
        return []

    loc = valid[LOC_COLUMN]
    revisions = valid[CHANGE_COLUMN]
    if len(valid) < 2 or loc.nunique() < 2 or revisions.nunique() < 2:
        statistics = [
            ("kendall", math.nan, math.nan),
            ("spearman", math.nan, math.nan),
            ("pearson", math.nan, math.nan),
        ]
    else:
        kendall = kendalltau(loc, revisions)
        spearman = spearmanr(loc, revisions)
        pearson = pearsonr(loc, revisions)
        statistics = [
            ("kendall", float(kendall.statistic), float(kendall.pvalue)),
            ("spearman", float(spearman.statistic), float(spearman.pvalue)),
            ("pearson", float(pearson.statistic), float(pearson.pvalue)),
        ]

    common = {
        "tool": tool,
        "method_kind": TEST_REVISION_METHOD_KIND,
        "change": CHANGE_COLUMN,
        "methods": len(valid),
        "loc_init_min": int(loc.min()),
        "loc_init_median": round(float(loc.median()), 2),
        "loc_init_max": int(loc.max()),
        "revision_min": int(revisions.min()),
        "revision_median": round(float(revisions.median()), 2),
        "revision_max": int(revisions.max()),
    }
    return [
        {
            **common,
            "correlation_algorithm": algorithm,
            "correlation": round(correlation, 4) if pd.notna(correlation) else math.nan,
            "p_value": p_value,
        }
        for algorithm, correlation, p_value in statistics
    ]


def load_tool_history(
    experiment_directory: Path,
    tool: str,
    selected_projects: list[str] | None,
) -> pd.DataFrame:
    csv_files = list_csv_files(
        experiment_directory / "method-history" / tool,
        selected_projects,
        strict=False,
    )
    frames = [
        pd.read_csv(csv_file, keep_default_na=False, na_filter=False, low_memory=False)
        for csv_file in csv_files
    ]
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    stats = GenerationStats("artifact_revision_loc_correlation")
    experiment_directory = resolve_experiment_paths(
        getattr(args, "workspace_directory", None),
        args.experiment_name,
    ).experiment_directory
    output_file = experiment_directory / "aggregate" / OUTPUT_FILE_NAME
    if not should_generate(output_file, replace=args.replace, label=OUTPUT_FILE_NAME, stats=stats):
        stats.print_summary()
        return

    selected_tools, selected_projects, _ = resolve_experiment_filters(
        tools=args.tools,
        projects=args.projects,
    )
    method_history_directory = experiment_directory / "method-history"
    if not method_history_directory.exists():
        warnings.warn(f"Directory not found, skipping: {method_history_directory}")
        stats.skipped_missing_input += 1
        stats.print_summary()
        return

    tools = select_named_items(
        util.sorted_directory_names(method_history_directory),
        selected_tools,
        item_label="tool",
    )
    rows = []
    for tool in tools:
        history = load_tool_history(experiment_directory, tool, selected_projects)
        if history.empty:
            continue
        if LOC_COLUMN not in history.columns or CHANGE_COLUMN not in history.columns:
            warnings.warn(
                f"Skipping tool={tool}: method-history data must include "
                f"{LOC_COLUMN} and {CHANGE_COLUMN}. Run ptc.generator.artifact_revision first."
            )
            continue
        filtered = filter_revision_method_base_population(history)
        rows.extend(correlation_rows(filtered, tool=tool))

    os.makedirs(output_file.parent, exist_ok=True)
    output_df = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    if not output_df.empty:
        algorithm_order = {"kendall": 0, "spearman": 1, "pearson": 2}
        output_df["_algorithm_order"] = output_df["correlation_algorithm"].map(algorithm_order)
        output_df = (
            output_df.sort_values(["tool", "_algorithm_order"])
            .drop(columns="_algorithm_order")
            .reset_index(drop=True)
        )
    output_df.to_csv(output_file, index=False)
    if output_df.empty:
        stats.record_empty_output()
    stats.record_write(len(output_df))
    print(f"Wrote {output_file}")
    stats.print_summary()


if __name__ == "__main__":
    main()

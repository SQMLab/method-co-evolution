import os
import warnings

import pandas as pd

import mhc.util as util
from mhc.command_util import (
    build_experiment_parser,
    filter_artifact_dataframe,
    resolve_experiment_filters,
    resolve_experiment_paths,
    select_named_items,
)
from ptc.generator.run_stats import GenerationStats, should_generate, unlink_stale_output
from ptc.util.helper import filter_revision_method_population_with_code


def build_parser():
    return build_experiment_parser(
        "Generate RQ3 filtered method artifact revision data.",
        include_tools=False,
        include_strategies=False,
        include_replace=True,
        projects_help="Comma-separated project names to process.",
    )


def drop_filter_only_columns(df: pd.DataFrame) -> pd.DataFrame:
    return df.drop(columns=[column for column in ["code"] if column in df.columns])


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    stats = GenerationStats("filter_artifact")
    experiment_directory = resolve_experiment_paths(
        getattr(args, "workspace_directory", None),
        args.experiment_name,
    ).experiment_directory
    _, selected_projects, _ = resolve_experiment_filters(
        projects=args.projects,
    )

    repository_df = pd.read_csv(experiment_directory / "project.csv")
    projects = select_named_items(repository_df["project"].tolist(), selected_projects, item_label="project")
    for project in projects:
        method_file = util.format_method_list_file(str(experiment_directory), project)
        output_file = experiment_directory / "method-artifact-filtered" / f"{project}.csv"
        if not os.path.exists(method_file):
            unlink_stale_output(
                output_file,
                reason=f"Skipping: {project} (missing method file)",
                stats=stats,
            )
            continue
        if not should_generate(output_file, replace=args.replace, label=project, stats=stats):
            continue

        df = pd.read_csv(method_file, keep_default_na=False, na_filter=False, low_memory=False)
        if df.empty:
            output_df = df.copy()
        else:
            output_df = filter_revision_method_population_with_code(
                filter_artifact_dataframe(df),
                experiment_directory,
            )
            output_df = drop_filter_only_columns(output_df)

        os.makedirs(output_file.parent, exist_ok=True)
        output_df.to_csv(output_file, index=False)
        if output_df.empty:
            stats.record_empty_output()
        stats.record_write(len(output_df))

    stats.print_summary()


if __name__ == "__main__":
    main()

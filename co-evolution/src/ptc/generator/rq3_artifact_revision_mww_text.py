import pandas as pd

from ptc.constants import ALL_REPOSITORY
from ptc.plot_util import build_experiment_plot_parser, resolve_experiment_paths

DEFAULT_TOOL = "historyFinder"
DEFAULT_CHANGE = "diff"
SIGNIFICANCE_THRESHOLD = 0.05
EFFECT_SIZE_ORDER = ["negligible", "small", "medium", "large"]


def build_parser():
    parser = build_experiment_plot_parser(
        "Generate RQ3 artifact revision MWU result text.",
        include_tools=True,
        include_strategies=False,
        include_project_directory=True,
        include_output_directory=True,
    )
    parser.add_argument(
        "--change",
        default=DEFAULT_CHANGE,
        help=f"MWU change category to summarize. Defaults to {DEFAULT_CHANGE}.",
    )
    return parser


def format_number(value: object) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value):.2f}"


def format_count(value: int) -> str:
    return f"{value:,}"


def format_project_count(value: int) -> str:
    noun = "project" if value == 1 else "projects"
    return f"{format_count(value)} {noun}"


def format_p_value(value: object) -> str:
    p_value = pd.to_numeric(value, errors="coerce")
    if pd.notna(p_value) and p_value < SIGNIFICANCE_THRESHOLD:
        return r"$p < 0.05$"
    return rf"$p={format_number(value)}$"


def overall_direction(sign: str) -> str:
    if sign == "+":
        return "production methods revised more frequently"
    if sign == "-":
        return "test methods revised more frequently"
    return "neither method category revised more frequently"


def direction_label(sign: str) -> str:
    if sign == "-":
        return "test methods were revised more frequently than production methods"
    if sign == "+":
        return "production methods were revised more frequently than test methods"
    return "test and production methods had tied revision counts"


def effect_percentages(rows: pd.DataFrame) -> str:
    total = len(rows)
    if total == 0:
        return "no effect-size percentages were computed"

    parts = []
    counts = rows["effect_size"].value_counts()
    for effect_size in EFFECT_SIZE_ORDER:
        count = int(counts.get(effect_size, 0))
        percent = (count / total) * 100
        parts.append(f"{effect_size} in {percent:.1f}\\%")
    return ", ".join(parts[:-1]) + f", and {parts[-1]}"


def summarize_direction(project_df: pd.DataFrame, sign: str) -> dict[str, object]:
    direction_df = project_df[project_df["d_sign"] == sign].copy()
    p_values = pd.to_numeric(direction_df["mww_p"], errors="coerce")
    significant_df = direction_df[p_values <= SIGNIFICANCE_THRESHOLD].copy()
    return {
        "count": len(direction_df),
        "significant_count": len(significant_df),
        "effect_percentages": effect_percentages(significant_df),
    }


def render_summary_text(table_df: pd.DataFrame) -> str:
    overall_df = table_df[table_df["project"] == ALL_REPOSITORY]
    if overall_df.empty:
        raise ValueError("RQ3 MWU summary requires an all-project row.")

    overall = overall_df.iloc[0]
    project_df = table_df[table_df["project"] != ALL_REPOSITORY].copy()
    test_summary = summarize_direction(project_df, "-")
    production_summary = summarize_direction(project_df, "+")
    overall_effect_size = str(overall["effect_size"])

    return (
        "We used the non-parametric Wilcoxon rank-sum test and found this "
        f"difference to be statistically significant ({format_p_value(overall['mww_p'])}). "
        "Furthermore, the non-parametric Cliff's delta indicates a "
        f"{overall_effect_size} effect size "
        rf"(Cliff's~$\delta={format_number(overall['d_value'])}$), with "
        f"{overall_direction(str(overall['d_sign']))} overall. "
        "We also performed the analysis at the project level, with the results "
        r"presented in Table~\ref{tab:artifact-revision-mww}. "
        f"We found that {direction_label('-')} in {format_project_count(test_summary['count'])}, "
        "with statistically significant differences in "
        f"{format_project_count(test_summary['significant_count'])}. "
        "Among these statistically significant projects, the corresponding effect sizes were "
        f"{test_summary['effect_percentages']}. "
        f"In contrast, {direction_label('+')} in {format_project_count(production_summary['count'])}, "
        "with statistically significant differences in "
        f"{format_project_count(production_summary['significant_count'])}. "
        "Among these statistically significant projects, the corresponding effect sizes were "
        f"{production_summary['effect_percentages']}."
    )


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    experiment_directory = resolve_experiment_paths(
        getattr(args, "workspace_directory", None),
        args.experiment_name,
    ).experiment_directory
    stats_file = experiment_directory / "aggregate" / "artifact-revision-mww.csv"
    if not stats_file.exists():
        raise FileNotFoundError(f"Stats file not found: {stats_file}")

    df = pd.read_csv(stats_file, keep_default_na=False, na_values=[""])
    tool = args.tools or DEFAULT_TOOL
    tool_df = df[(df["tool"] == tool) & (df["change"] == args.change)].copy()
    if tool_df.empty:
        raise ValueError(f"No artifact revision MWU rows found for tool={tool}, change={args.change}.")

    print(render_summary_text(tool_df))


if __name__ == "__main__":
    main()

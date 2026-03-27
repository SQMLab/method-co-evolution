from pathlib import Path
import operator
import random

import pandas as pd

from mhc.config import DATA_DIRECTORY
from ptc.link_strategy import LinkStrategy, keys_from_mask


def _strategy_key(strategy: str | LinkStrategy) -> str:
    if isinstance(strategy, LinkStrategy):
        return "--".join(keys_from_mask(strategy))
    return "--".join(part.strip().lower() for part in strategy.split("--") if part.strip())


def _apply_filter(
    frame: pd.DataFrame,
    left_column: str | None,
    comparison_operator: str | None,
    right_column: str | None,
) -> pd.DataFrame:
    if left_column is None and comparison_operator is None and right_column is None:
        return frame

    if not left_column or not comparison_operator or not right_column:
        raise ValueError("left_column, comparison_operator, and right_column must be passed together")

    operations = {
        ">": operator.gt,
        ">=": operator.ge,
        "<": operator.lt,
        "<=": operator.le,
        "==": operator.eq,
        "!=": operator.ne,
    }
    if comparison_operator not in operations:
        raise ValueError("comparison_operator must be one of: >, >=, <, <=, ==, !=")

    if left_column not in frame.columns or right_column not in frame.columns:
        raise ValueError(f"Missing column(s): {left_column}, {right_column}")

    left_values = pd.to_numeric(frame[left_column], errors="coerce")
    right_values = pd.to_numeric(frame[right_column], errors="coerce")
    mask = operations[comparison_operator](left_values, right_values).fillna(False)
    return frame.loc[mask].copy()


def main(
    tool_name: str,
    method_linking_strategy: str | LinkStrategy,
    max_samples_per_project: int,
    number_of_projects: int,
    seed: int = 42,
    left_column: str | None = None,
    comparison_operator: str | None = None,
    right_column: str | None = None,
) -> Path:
    strategy_key = _strategy_key(method_linking_strategy)
    input_directory = Path(DATA_DIRECTORY) / "t2p-change" / tool_name / strategy_key
    output_directory = Path(DATA_DIRECTORY) / "t2p-change-sample" / tool_name / strategy_key
    output_directory.mkdir(parents=True, exist_ok=True)

    project_files = sorted(input_directory.glob("*.csv"))
    if not project_files:
        raise FileNotFoundError(f"No csv files found in {input_directory}")

    random_generator = random.Random(seed)
    project_data = {}

    for project_file in project_files:
        project_name = project_file.stem
        project_df = pd.read_csv(project_file, keep_default_na=False, na_filter=False)
        project_df = _apply_filter(project_df, left_column, comparison_operator, right_column)
        if not project_df.empty:
            project_data[project_name] = project_df

    if not project_data:
        raise ValueError("No rows left after applying the filter")

    if max_samples_per_project <= 0:
        raise ValueError("max_samples_per_project must be greater than 0")

    if number_of_projects <= 0:
        raise ValueError("number_of_projects must be greater than 0")

    available_project_names = sorted(project_data)
    selected_project_names = sorted(
        random_generator.sample(
            available_project_names,
            k=min(number_of_projects, len(available_project_names)),
        )
    )

    sampled_frames = []
    summary_rows = []

    for project_name in selected_project_names:
        project_df = project_data[project_name]
        sample_size = min(max_samples_per_project, len(project_df))
        sampled_df = project_df.sample(n=sample_size, random_state=random_generator.randint(0, 10**9)).copy()
        sampled_df["project"] = project_name

        sampled_df.to_csv(output_directory / f"{project_name}.csv", index=False)
        sampled_frames.append(sampled_df)
        summary_rows.append(
            {
                "project": project_name,
                "available_rows": len(project_df),
                "sampled_rows": sample_size,
            }
        )

    pd.DataFrame(summary_rows).to_csv(output_directory / "summary.csv", index=False)
    pd.concat(sampled_frames, ignore_index=True).to_csv(output_directory / "all-projects.csv", index=False)
    return output_directory


if __name__ == "__main__":
    output_dir = main(
        tool_name="historyFinder",
        method_linking_strategy="omc--nc--ncc",
        max_samples_per_project=4,
        number_of_projects=5,
        seed=42,
        left_column="from_ch_diff",
        comparison_operator=">",
        right_column="to_ch_diff",
    )
    print(output_dir)

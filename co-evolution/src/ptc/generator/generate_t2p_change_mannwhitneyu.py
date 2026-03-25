import os
from pathlib import Path

import numpy as np
import pandas as pd

import mhc.util as util
from mhc.config import CACHE_DIRECTORY, DATA_DIRECTORY
from ptc.constants import ALL_REPOSITORY, CODE_SHOVEL_UNSUPPORTED_CHANGES
from ptc.plot_util import man_utest

STAT_COLUMNS = ["project", "tool", "strategy", "change", "corr", "stat_stat", "stat_p", "stat_d", "stat_size"]
code_shovel_unsupported_change_set = {
    f"ch_{change_type.name.lower()}" for change_type in CODE_SHOVEL_UNSUPPORTED_CHANGES
}


def build_stat_row(project: str, tool: str, strategy: str, change: str, pair_df: pd.DataFrame) -> dict | None:
    if pair_df.empty:
        return None

    x = pair_df[f"to_{change}"]
    y = pair_df[f"from_{change}"]
    if x.empty or y.empty:
        return None

    if len(pair_df) < 2 or x.std() == 0 or y.std() == 0:
        corr = np.nan
    else:
        corr = x.corr(y, method="kendall")

    stat, p_value, d, size = man_utest(x, y)
    return {
        "project": project,
        "tool": tool,
        "strategy": strategy,
        "change": change.replace("ch_", ""),
        "corr": round(corr, 2) if pd.notna(corr) else np.nan,
        "stat_stat": round(stat, 2),
        "stat_p": round(p_value, 2),
        "stat_d": round(d, 2),
        "stat_size": size,
    }


def main() -> None:
    stats_rows = []

    tools = util.sorted_directory_names(f"{DATA_DIRECTORY}/t2p-change")
    for tool in tools:
        for strategy in util.sorted_directory_names(f"{DATA_DIRECTORY}/t2p-change/{tool}"):
            history_repository_dfs = [
                pd.read_csv(repository_history_file, keep_default_na=False, na_filter=False)
                for repository_history_file in list(Path(f"{DATA_DIRECTORY}/t2p-change/{tool}/{strategy}").rglob("*.csv"))[
                    :int(os.getenv("METHOD_EVOLUTION_EXPERIMENT_REPOSITORY_COUNT", -1))
                ]
            ]
            history_repository_dfs = [df for df in history_repository_dfs if not df.empty]
            if not history_repository_dfs:
                continue

            df = pd.concat(history_repository_dfs)
            for prefix in ["from_", "to_"]:
                df[f"{prefix}artifact"] = df[f"{prefix}artifact"].map(lambda mt: "test" if mt == "test_util" else mt)

            change_cols = [c[len("from_"):] for c in df.columns if c.startswith("from_ch_")]
            projects = sorted(df["project"].unique(), key=lambda x: x.lower())
            projects.append(ALL_REPOSITORY)

            for project in projects:
                project_df = df if project == ALL_REPOSITORY else df[df["project"] == project]
                for change in change_cols:
                    if tool == "codeShovel" and change in code_shovel_unsupported_change_set:
                        continue

                    pair_df = project_df[[f"to_{change}", f"from_{change}"]].dropna()
                    stat_row = build_stat_row(project, tool, strategy, change, pair_df)
                    if stat_row is not None:
                        stats_rows.append(stat_row)

    stats_output_file = f"{CACHE_DIRECTORY}/data/aggregate/t2p-change-scatter-stats.csv"
    os.makedirs(os.path.dirname(stats_output_file), exist_ok=True)
    stats_df = pd.DataFrame(stats_rows, columns=STAT_COLUMNS)
    stats_df = stats_df.sort_values(["project", "tool", "strategy", "change"]).reset_index(drop=True)
    stats_df.to_csv(stats_output_file, index=False)


if __name__ == "__main__":
    main()

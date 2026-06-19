from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from mhc.command_util import (
    build_experiment_parser,
    resolve_experiment_filters,
    resolve_experiment_paths,
    select_named_items,
)
from ptc.plot.method_history_runtime_table import resolve_path


DEFAULT_LEFT_GROUND_TRUTH = Path("data") / "t2plinker" / "t2p-ground-truth"
DEFAULT_RIGHT_GROUND_TRUTH = Path("data") / "t2plinker" / "t2p-ground-truth-2"
DISAGREEMENT_DIRECTORY_NAME = "t2p-ground-truth-disagreement"
SUMMARY_FILE_NAME = "agreement-summary.csv"
REQUIRED_COLUMNS = {"from_url", "to_url", "label"}
KEY_COLUMNS = ["from_url", "to_url"]
METADATA_COLUMNS = ["from_name", "to_name", "tags", "notes", "candidate"]
DISAGREEMENT_COLUMNS = [
    "project",
    "from_url",
    "to_url",
    "from_name",
    "to_name",
    "left_label",
    "right_label",
    "disagreement",
    "left_tags",
    "right_tags",
    "left_notes",
    "right_notes",
    "left_candidate",
    "right_candidate",
]
SUMMARY_COLUMNS = [
    "project",
    "left_pairs",
    "right_pairs",
    "union_pairs",
    "agreements",
    "disagreements",
    "only_left",
    "only_right",
    "unlabeled_or_invalid",
    "percent_agreement",
    "cohen_kappa",
]
BINARY_LABELS = {"0", "1"}


def build_parser():
    parser = build_experiment_parser(
        "Compare two T2P ground-truth directories and report agreement.",
        include_tools=False,
        include_strategies=False,
        include_projects=True,
        include_project_directory=True,
        projects_help="Comma-separated project names to compare. Defaults to ME_PROJECTS.",
    )
    parser.add_argument(
        "--left-ground-truth-dir",
        default=None,
        help="Defaults to <project-directory>/data/t2plinker/t2p-ground-truth.",
    )
    parser.add_argument(
        "--right-ground-truth-dir",
        default=None,
        help="Defaults to <project-directory>/data/t2plinker/t2p-ground-truth-2.",
    )
    return parser


def _label(value: object) -> str:
    return str(value).strip()


def _is_binary_label(value: object) -> bool:
    return _label(value) in BINARY_LABELS


def _read_ground_truth_file(csv_file: Path, side: str) -> pd.DataFrame:
    df = pd.read_csv(csv_file, keep_default_na=False, na_filter=False, low_memory=False)
    missing_columns = sorted(REQUIRED_COLUMNS - set(df.columns))
    if missing_columns:
        raise ValueError(
            f"{side} ground truth {csv_file} is missing required column(s): "
            + ", ".join(missing_columns)
        )

    for column in METADATA_COLUMNS:
        if column not in df.columns:
            df[column] = ""

    df = df[KEY_COLUMNS + ["label", *METADATA_COLUMNS]].copy()
    df["label"] = df["label"].map(_label)

    duplicate_groups = df.groupby(KEY_COLUMNS, dropna=False)["label"].nunique()
    conflicting = duplicate_groups[duplicate_groups > 1]
    if not conflicting.empty:
        examples = [
            f"({from_url}, {to_url})"
            for from_url, to_url in list(conflicting.index[:3])
        ]
        raise ValueError(
            f"{side} ground truth {csv_file} has conflicting duplicate labels for: "
            + ", ".join(examples)
        )

    return df.drop_duplicates(subset=KEY_COLUMNS, keep="first").reset_index(drop=True)


def _empty_ground_truth_df() -> pd.DataFrame:
    return pd.DataFrame(columns=KEY_COLUMNS + ["label", *METADATA_COLUMNS])


def _prefixed(df: pd.DataFrame, side: str) -> pd.DataFrame:
    return df.rename(
        columns={
            "label": f"{side}_label",
            "tags": f"{side}_tags",
            "notes": f"{side}_notes",
            "candidate": f"{side}_candidate",
        }
    )


def cohen_kappa(labels_left: pd.Series, labels_right: pd.Series) -> float:
    if labels_left.empty:
        return np.nan

    observed = float((labels_left == labels_right).mean())
    left_counts = labels_left.value_counts(normalize=True)
    right_counts = labels_right.value_counts(normalize=True)
    expected = sum(
        float(left_counts.get(label, 0.0)) * float(right_counts.get(label, 0.0))
        for label in BINARY_LABELS
    )
    if expected == 1.0:
        return 1.0 if observed == 1.0 else np.nan
    return (observed - expected) / (1.0 - expected)


def _disagreement_reason(row: pd.Series) -> str:
    in_left = bool(row["_in_left"])
    in_right = bool(row["_in_right"])
    if not in_left:
        return "only_right"
    if not in_right:
        return "only_left"

    left_binary = _is_binary_label(row["left_label"])
    right_binary = _is_binary_label(row["right_label"])
    if not left_binary or not right_binary:
        return "unlabeled_or_invalid"
    return "label_mismatch"


def compare_project(
    project: str,
    left_file: Path | None,
    right_file: Path | None,
) -> tuple[pd.DataFrame, dict[str, object]]:
    left_df = (
        _read_ground_truth_file(left_file, "left")
        if left_file is not None and left_file.exists()
        else _empty_ground_truth_df()
    )
    right_df = (
        _read_ground_truth_file(right_file, "right")
        if right_file is not None and right_file.exists()
        else _empty_ground_truth_df()
    )

    merged_df = _prefixed(left_df, "left").merge(
        _prefixed(right_df, "right"),
        on=KEY_COLUMNS,
        how="outer",
        suffixes=("_left", "_right"),
        indicator=True,
    )
    merged_df["_in_left"] = merged_df["_merge"].isin(["left_only", "both"])
    merged_df["_in_right"] = merged_df["_merge"].isin(["right_only", "both"])

    for column in [
        "left_label",
        "right_label",
        "left_tags",
        "right_tags",
        "left_notes",
        "right_notes",
        "left_candidate",
        "right_candidate",
        "from_name_left",
        "from_name_right",
        "to_name_left",
        "to_name_right",
    ]:
        if column in merged_df.columns:
            merged_df[column] = merged_df[column].fillna("")

    left_binary = merged_df["left_label"].map(_is_binary_label)
    right_binary = merged_df["right_label"].map(_is_binary_label)
    binary_comparable = merged_df["_in_left"] & merged_df["_in_right"] & left_binary & right_binary
    agreement_mask = binary_comparable & (merged_df["left_label"] == merged_df["right_label"])
    disagreement_mask = ~agreement_mask
    only_left = int((merged_df["_in_left"] & ~merged_df["_in_right"]).sum())
    only_right = int((~merged_df["_in_left"] & merged_df["_in_right"]).sum())
    unlabeled_or_invalid = int((merged_df["_in_left"] & merged_df["_in_right"] & ~(left_binary & right_binary)).sum())
    union_pairs = len(merged_df)
    agreements = int(agreement_mask.sum())
    disagreements = int(union_pairs - agreements)
    percent_agreement = agreements / union_pairs if union_pairs else np.nan
    kappa = cohen_kappa(
        merged_df.loc[binary_comparable, "left_label"],
        merged_df.loc[binary_comparable, "right_label"],
    )

    mismatches = merged_df.loc[disagreement_mask].copy()
    if mismatches.empty:
        disagreement_df = pd.DataFrame(columns=DISAGREEMENT_COLUMNS)
    else:
        disagreement_df = pd.DataFrame(
            {
                "project": project,
                "from_url": mismatches["from_url"],
                "to_url": mismatches["to_url"],
                "from_name": mismatches["from_name_left"].where(
                    mismatches["from_name_left"].astype(str) != "",
                    mismatches["from_name_right"],
                ),
                "to_name": mismatches["to_name_left"].where(
                    mismatches["to_name_left"].astype(str) != "",
                    mismatches["to_name_right"],
                ),
                "left_label": mismatches["left_label"],
                "right_label": mismatches["right_label"],
                "disagreement": mismatches.apply(_disagreement_reason, axis=1),
                "left_tags": mismatches["left_tags"],
                "right_tags": mismatches["right_tags"],
                "left_notes": mismatches["left_notes"],
                "right_notes": mismatches["right_notes"],
                "left_candidate": mismatches["left_candidate"],
                "right_candidate": mismatches["right_candidate"],
            },
            columns=DISAGREEMENT_COLUMNS,
        ).sort_values(KEY_COLUMNS).reset_index(drop=True)

    summary = {
        "project": project,
        "left_pairs": len(left_df),
        "right_pairs": len(right_df),
        "union_pairs": union_pairs,
        "agreements": agreements,
        "disagreements": disagreements,
        "only_left": only_left,
        "only_right": only_right,
        "unlabeled_or_invalid": unlabeled_or_invalid,
        "percent_agreement": percent_agreement,
        "cohen_kappa": kappa,
        "_binary_00": int(((merged_df.loc[binary_comparable, "left_label"] == "0") & (merged_df.loc[binary_comparable, "right_label"] == "0")).sum()),
        "_binary_01": int(((merged_df.loc[binary_comparable, "left_label"] == "0") & (merged_df.loc[binary_comparable, "right_label"] == "1")).sum()),
        "_binary_10": int(((merged_df.loc[binary_comparable, "left_label"] == "1") & (merged_df.loc[binary_comparable, "right_label"] == "0")).sum()),
        "_binary_11": int(((merged_df.loc[binary_comparable, "left_label"] == "1") & (merged_df.loc[binary_comparable, "right_label"] == "1")).sum()),
    }
    return disagreement_df, summary


def _project_files(directory: Path) -> dict[str, Path]:
    if not directory.is_dir():
        raise FileNotFoundError(f"Ground-truth directory not found: {directory}")
    return {csv_file.stem: csv_file for csv_file in directory.glob("*.csv")}


def compare_directories(
    left_directory: Path,
    right_directory: Path,
    selected_projects: list[str] | None = None,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    left_files = _project_files(left_directory)
    right_files = _project_files(right_directory)
    projects = sorted(set(left_files) | set(right_files))
    projects = select_named_items(
        projects,
        selected_projects,
        item_label="project",
        strict=True,
    )

    disagreement_by_project = {}
    summary_rows = []
    for project in projects:
        disagreement_df, summary = compare_project(
            project,
            left_files.get(project),
            right_files.get(project),
        )
        disagreement_by_project[project] = disagreement_df
        summary_rows.append(summary)

    summary_df = pd.DataFrame(summary_rows)
    total_row = summarize_total(summary_df)
    summary_df = summary_df[SUMMARY_COLUMNS]
    return disagreement_by_project, pd.concat([summary_df, pd.DataFrame([total_row])], ignore_index=True)


def summarize_total(summary_df: pd.DataFrame) -> dict[str, object]:
    if summary_df.empty:
        return {
            "project": "total",
            "left_pairs": 0,
            "right_pairs": 0,
            "union_pairs": 0,
            "agreements": 0,
            "disagreements": 0,
            "only_left": 0,
            "only_right": 0,
            "unlabeled_or_invalid": 0,
            "percent_agreement": np.nan,
            "cohen_kappa": np.nan,
        }

    totals = {
        column: int(summary_df[column].sum())
        for column in [
            "left_pairs",
            "right_pairs",
            "union_pairs",
            "agreements",
            "disagreements",
            "only_left",
            "only_right",
            "unlabeled_or_invalid",
        ]
    }
    percent_agreement = (
        totals["agreements"] / totals["union_pairs"]
        if totals["union_pairs"]
        else np.nan
    )
    binary_00 = int(summary_df["_binary_00"].sum())
    binary_01 = int(summary_df["_binary_01"].sum())
    binary_10 = int(summary_df["_binary_10"].sum())
    binary_11 = int(summary_df["_binary_11"].sum())
    binary_total = binary_00 + binary_01 + binary_10 + binary_11
    if binary_total:
        total_left = pd.Series(["0"] * (binary_00 + binary_01) + ["1"] * (binary_10 + binary_11))
        total_right = pd.Series(["0"] * binary_00 + ["1"] * binary_01 + ["0"] * binary_10 + ["1"] * binary_11)
        total_kappa = cohen_kappa(total_left, total_right)
    else:
        total_kappa = np.nan

    return {
        "project": "total",
        **totals,
        "percent_agreement": percent_agreement,
        "cohen_kappa": total_kappa,
    }


def write_outputs(
    disagreement_by_project: dict[str, pd.DataFrame],
    summary_df: pd.DataFrame,
    disagreement_directory: Path,
    summary_file: Path,
) -> None:
    disagreement_directory.mkdir(parents=True, exist_ok=True)
    summary_file.parent.mkdir(parents=True, exist_ok=True)
    for project, disagreement_df in disagreement_by_project.items():
        disagreement_df.to_csv(disagreement_directory / f"{project}.csv", index=False)
    summary_df.to_csv(summary_file, index=False)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    project_directory = Path(args.project_directory)
    paths = resolve_experiment_paths(args.workspace_directory, args.experiment_name)
    left_directory = resolve_path(
        project_directory,
        args.left_ground_truth_dir,
        DEFAULT_LEFT_GROUND_TRUTH,
    )
    right_directory = resolve_path(
        project_directory,
        args.right_ground_truth_dir,
        DEFAULT_RIGHT_GROUND_TRUTH,
    )
    disagreement_directory = paths.experiment_directory / DISAGREEMENT_DIRECTORY_NAME
    summary_file = paths.experiment_directory / "aggregate" / SUMMARY_FILE_NAME
    _, selected_projects, _ = resolve_experiment_filters(projects=args.projects)

    disagreement_by_project, summary_df = compare_directories(
        left_directory,
        right_directory,
        selected_projects,
    )
    write_outputs(disagreement_by_project, summary_df, disagreement_directory, summary_file)

    total = summary_df[summary_df["project"] == "total"].iloc[0]
    total_kappa = pd.to_numeric(pd.Series([total["cohen_kappa"]]), errors="coerce").iloc[0]
    print(f"Wrote disagreement CSVs: {disagreement_directory}")
    print(f"Wrote agreement summary: {summary_file}")
    print(f"Total percent agreement: {float(total['percent_agreement']):.4f}")
    print(f"Total Cohen's kappa: {total_kappa:.4f}" if not np.isnan(total_kappa) else "Total Cohen's kappa: NaN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

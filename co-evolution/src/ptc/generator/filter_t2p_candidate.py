from pathlib import Path

import pandas as pd

from mhc.config import DATA_DIRECTORY
from ptc.experiment_util import build_experiment_parser, list_csv_files, resolve_experiment_filters


EXPANDED_T2P_CANDIDATE_DIR = Path(DATA_DIRECTORY) / "t2p-candidate-expanded"
FILTERED_T2P_CANDIDATE_DIR = Path(DATA_DIRECTORY) / "t2p-candidate-filtered"
UNNEEDED_CANDIDATE_COLUMNS = ["from_fqs_alt", "to_fqs_alt"]

FILTERED_T2P_CANDIDATE_DIR.mkdir(parents=True, exist_ok=True)


def build_parser():
    return build_experiment_parser(
        "Filter expanded test-to-production candidates.",
        include_tools=False,
        include_strategies=False,
        projects_help="Comma-separated project names to process.",
    )


def filter_candidate_df(candidate_df: pd.DataFrame) -> pd.DataFrame:
    return candidate_df.drop(columns=UNNEEDED_CANDIDATE_COLUMNS, errors="ignore").copy()


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    _, selected_projects, _ = resolve_experiment_filters(
        use_filters=args.use_filters,
        projects=args.projects,
    )

    for candidate_file in list_csv_files(EXPANDED_T2P_CANDIDATE_DIR, selected_projects, strict=False):
        print("Processing:", candidate_file.stem)
        candidate_df = pd.read_csv(candidate_file, keep_default_na=False, na_filter=False)
        filtered_df = filter_candidate_df(candidate_df)
        output_file = FILTERED_T2P_CANDIDATE_DIR / candidate_file.name
        filtered_df.to_csv(output_file, index=False)

    print("Finished.")


if __name__ == "__main__":
    main()

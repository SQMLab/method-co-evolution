from __future__ import annotations

from pathlib import Path

import pandas as pd

from mhc.config import PROJECT_DIRECTORY

RANDOM_SEED = 42
TOTAL_SAMPLE = 400
EXCLUDE_PROJECTS = {"okhttp"}
GROUND_TRUTH_COLUMNS = [
    "project",
    "from_name",
    "to_name",
    "from_url",
    "to_url",
    "from_fqs",
    "from_tctracer_fqs",
    "from_testlinker_fqs",
    "to_fqs",
    "to_tctracer_fqs",
    "to_testlinker_fqs",
    "label",
]

_PROJECT_DIR = Path(PROJECT_DIRECTORY)
_WORKSPACE = _PROJECT_DIR / "workspace"
REPOSITORY_FILE = _WORKSPACE / "data" / "repository" / "repository.csv"
CALLGRAPH_DIR = _WORKSPACE / "data" / "callgraph"
METHOD_DIR = _WORKSPACE / "data" / "method"

OUTPUT_DIR = Path(_WORKSPACE) / "data" / "ground-truth" / "t2plinker-t2p-ground-truth"


def _load_grund_projects() -> list[str]:
    repo_df = pd.read_csv(REPOSITORY_FILE, keep_default_na=False, na_filter=False)
    projects = (
        repo_df[repo_df["ref"].str.contains("grund", na=False)]["project"]
        .tolist()
    )
    return [p for p in projects if p not in EXCLUDE_PROJECTS]


def _test_caller_urls(project: str) -> pd.DataFrame:
    """Return unique test-method rows from callgraph: from_url, from_name, from_fqs."""
    cg_file = CALLGRAPH_DIR / f"{project}.csv"
    method_file = METHOD_DIR / f"{project}.csv"

    if not cg_file.exists() or not method_file.exists():
        return pd.DataFrame(columns=["from_url", "from_name", "from_fqs"])

    method_df = pd.read_csv(method_file, keep_default_na=False, na_filter=False, usecols=["url", "artifact"])
    test_urls = set(method_df[method_df["artifact"] == "test"]["url"])

    cg_df = pd.read_csv(cg_file, keep_default_na=False, na_filter=False, usecols=["from_url", "from_name", "from_fqs"])
    test_callers = (
        cg_df[cg_df["from_url"].isin(test_urls)]
        .drop_duplicates(subset=["from_url"])
        [["from_url", "from_name", "from_fqs"]]
        .reset_index(drop=True)
    )
    return test_callers


def main() -> None:
    projects = _load_grund_projects()
    print(f"grund projects (excl. okhttp): {len(projects)}")

    # Build pools first so we know how many projects have eligible data
    pools: list[tuple[str, pd.DataFrame]] = []
    for project in projects:
        pool = _test_caller_urls(project)
        if pool.empty:
            print(f"  {project}: no test callers in callgraph — skipped")
        else:
            pools.append((project, pool))

    n_eligible = len(pools)
    base_n = TOTAL_SAMPLE // n_eligible
    remainder = TOTAL_SAMPLE % n_eligible
    print(f"Eligible projects: {n_eligible}")
    print(f"Sample per project: {base_n} ({remainder} projects get {base_n + 1})")

    sampled_rows: list[pd.DataFrame] = []

    for i, (project, pool) in enumerate(pools):
        n = base_n + (1 if i < remainder else 0)

        if len(pool) < n:
            print(f"  {project}: only {len(pool)} available, wanted {n} — taking all")
            sample = pool
        else:
            sample = pool.sample(n=n, random_state=RANDOM_SEED)

        sample = sample.copy()
        sample["project"] = project
        sampled_rows.append((project, sample))
        print(f"  {project}: sampled {len(sample)} / {len(pool)} test methods")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    total = 0
    for project, sample in sampled_rows:
        output_df = pd.DataFrame(columns=GROUND_TRUTH_COLUMNS)
        for col in GROUND_TRUTH_COLUMNS:
            output_df[col] = sample.get(col, pd.NA) if col != "label" else pd.NA
        output_df = output_df[GROUND_TRUTH_COLUMNS]
        out_file = OUTPUT_DIR / f"{project}.csv"
        output_df.to_csv(out_file, index=False)
        total += len(output_df)
        print(f"  wrote {len(output_df)} rows → {out_file}")

    print(f"\nTotal: {total} rows across {len(sampled_rows)} files → {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

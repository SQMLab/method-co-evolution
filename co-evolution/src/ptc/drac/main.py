import argparse
import re
import sys
from pathlib import Path

import pandas as pd


_COMMAND_ALIASES = {
    "history": "method-history",
    "call-graph": "method-callgraph",
    "scan-method": "method-scan",
    "scan-class": "class-scan",
}

_ARRAY_RE = re.compile(r"--array=(\S+)")
_SPACED_RE = re.compile(r"--(?P<key>shards|command|workspace-directory|tool-name)\s+(\S+)")
_EQUALS_RE = re.compile(r"--(?P<key>shards|command|workspace-directory|tool-name)=(\S+)")


def _parse_arg(text: str, key: str) -> str | None:
    for pattern in (_SPACED_RE, _EQUALS_RE):
        for m in pattern.finditer(text):
            if m.group("key") == key:
                return m.group(2)
    return None


def _parse_index_ranges(array_str: str) -> list[tuple[int, int]]:
    """Parse a comma-separated list of project indices or index ranges.

    '0,10-15,22' -> [(0,0), (10,15), (22,22)]
    """
    result = []
    for part in array_str.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            result.append((int(start), int(end)))
        else:
            result.append((int(part), int(part)))
    return result


def _expand_indices(index_ranges: list[tuple[int, int]]) -> list[int]:
    """Expand index ranges to a flat sorted list of individual project indices."""
    indices = []
    for start, end in index_ranges:
        indices.extend(range(start, end + 1))
    return indices


def _group_consecutive(indices: list[int]) -> list[tuple[int, int]]:
    """Re-group a sorted list of project indices into contiguous ranges."""
    if not indices:
        return []
    groups = []
    start = prev = indices[0]
    for idx in indices[1:]:
        if idx == prev + 1:
            prev = idx
        else:
            groups.append((start, prev))
            start = prev = idx
    groups.append((start, prev))
    return groups


def _indices_to_task_ranges(index_groups: list[tuple[int, int]], shards: int) -> list[str]:
    """Convert project index groups to Slurm task ID range strings.

    Each project index i covers task IDs [i*shards, (i+1)*shards - 1].
    A group (a, b) of consecutive indices covers [a*shards, (b+1)*shards - 1].
    """
    result = []
    for start_idx, end_idx in index_groups:
        task_start = start_idx * shards
        task_end = (end_idx + 1) * shards - 1
        result.append(f"{task_start}-{task_end}")
    return result


def _load_repository(workspace_dir: str | Path) -> pd.DataFrame:
    path = Path(workspace_dir) / "data" / "repository" / "repository.csv"
    return pd.read_csv(path)


def _output_exists(command: str, workspace: str | Path, project: str, tool_name: str) -> bool:
    canonical = _COMMAND_ALIASES.get(command, command)
    base = Path(workspace)
    if canonical == "method-scan":
        return (base / "data" / "method" / f"{project}.csv").exists()
    if canonical == "method-callgraph":
        return (base / "data" / "callgraph" / f"{project}.csv").exists()
    if canonical == "method-history":
        return (base / "history" / tool_name / project).is_dir()
    if canonical == "method-code":
        return (base / "data" / "method-code" / f"{project}.csv").exists()
    return False


def process(
    text: str,
    repo_df: pd.DataFrame | None,
    replace: bool = False,
    workspace_override: str | None = None,
) -> str:
    array_match = _ARRAY_RE.search(text)
    if not array_match:
        raise ValueError("No --array= found in input")

    raw_shards = _parse_arg(text, "shards")
    if raw_shards is None:
        raise ValueError("No --shards found in input")
    shards = int(raw_shards)

    command = _parse_arg(text, "command")
    if command is None:
        raise ValueError("No --command found in input")

    workspace = workspace_override or _parse_arg(text, "workspace-directory")
    tool_name = _parse_arg(text, "tool-name") or ""

    index_ranges = _parse_index_ranges(array_match.group(1))
    indices = _expand_indices(index_ranges)

    if not replace and workspace is not None and repo_df is not None:
        indices = [
            idx for idx in indices
            if not _output_exists(command, workspace, str(repo_df.iloc[idx]["project"]), tool_name)
        ]

    if not indices:
        raise ValueError("No indices remaining after filtering existing outputs")

    groups = _group_consecutive(indices)
    task_ranges = _indices_to_task_ranges(groups, shards)
    new_array = ",".join(task_ranges)
    return text[: array_match.start()] + f"--array={new_array}" + text[array_match.end():]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Expand project indices in --array to Slurm task ID ranges."
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="Path to file containing the sbatch command (default: stdin)",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Include all indices even if output files already exist",
    )
    parser.add_argument(
        "--workspace-directory",
        dest="workspace_directory",
        default=None,
        help="Override workspace directory for repository.csv lookup and output existence checks",
    )
    args, extra = parser.parse_known_args()

    if extra or (args.input is not None and not Path(args.input).exists()):
        # Inline command passed directly: e.g. ptc-sbatch sbatch --array=22,29 --shards 200
        parts = ([args.input] if args.input is not None else []) + extra
        # --workspace-directory was consumed by our parser; restore it so the output is valid.
        if args.workspace_directory is not None and "--workspace-directory" not in parts:
            parts += ["--workspace-directory", args.workspace_directory]
        text = " ".join(parts)
    elif args.input is not None:
        text = Path(args.input).read_text()
    else:
        text = sys.stdin.read()

    workspace = args.workspace_directory or _parse_arg(text, "workspace-directory")
    repo_df = _load_repository(workspace) if workspace is not None else None
    result = process(text, repo_df, replace=args.replace, workspace_override=args.workspace_directory)
    print(result, end="")


if __name__ == "__main__":
    main()

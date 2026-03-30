import re
from ptc.constants import MethodChangeType


def extract_change_count(history_json) -> dict[str, int]:
    change_commits = history_json["changeHistoryDetails"]
    change_history = {f"ch_{ct.name.lower()}": 0 for ct in MethodChangeType}
    diff_commit_count = 0
    for commit_hash, commit_detail in change_commits.items():
        changes = {p.strip() for p in re.split(r'[(),]', commit_detail['type']) if
                   p.strip()}
        for change_type in changes:
            change_history[f"ch_{MethodChangeType(change_type).name.lower()}"] += 1
        if "diff" in commit_detail and commit_detail['diff']:
            diff_commit_count += 1
        elif "subchanges" in commit_detail:
            for subchange in commit_detail['subchanges']:
                if "diff" in subchange and subchange['diff']:
                    diff_commit_count += 1
                    break

    change_history["ch_all"] = len(change_commits)
    change_history["ch_diff"] = diff_commit_count
    return change_history

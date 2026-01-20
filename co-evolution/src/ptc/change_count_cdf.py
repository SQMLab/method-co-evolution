import pandas as pd
import os
from pathlib import Path
import tarfile
import json
import re
from ptc.constants import MethodChangeType
cache_dir = os.environ.get("METHOD_CO_EVOLUTION_CACHE_DIRECTORY")


for tooName in os.listdir(f"{cache_dir}/history"):
    if tooName.startswith("historyFinder"):
        continue
    for zip_file in Path(f"{cache_dir}/history/{tooName}").rglob("*.tar.gz"):
        method_history_list = []
        repository_name = zip_file.stem
        with tarfile.open(zip_file, "r:gz") as tar:
            for file in tar.getmembers():
                if file.isfile() and file.name.endswith(".json"):
                    _, base_file  = file.name.split("/", maxsplit= 1)
                    file_content = tar.extractfile(file)
                    if file_content is not None:
                        history_json = json.load(file_content)
                        change_commits = history_json["changeHistoryShort"]
                        change_history = {ct.value: 0 for ct in MethodChangeType}


                        # print(change_history)
                        for commit_hash, change_text in change_commits.items():
                            changes = [p.strip() for p in re.split(r'[(),]', change_text) if p.strip()]
                            for change_type in changes:
                                change_history[change_type] += 1
                        method_history = {"history_file" : base_file, "ch_all": len(change_commits)}
                        for key, value in change_history.items():
                            method_history[f"ch_{MethodChangeType(key).name.lower()}"] = value
                            method_history_list.append(method_history)
        repository_change_history_file = f"{cache_dir}/data/history/{tooName}/{repository_name}--history.csv"
        os.makedirs(os.path.dirname(repository_change_history_file), exist_ok=True)
        pd.DataFrame(method_history_list).to_csv(repository_change_history_file, index=False)
        break





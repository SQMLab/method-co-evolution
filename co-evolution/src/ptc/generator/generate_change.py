import json
import logging
import tarfile
import warnings
from pathlib import Path
import pandas as pd
import mhc.util as util
from ptc.util.helper import extract_change_count
from mhc.config import *


def main() -> None:
    repository_df = pd.read_csv(f"{DATA_DIRECTORY}/repository/repository.csv")
    repository_name_map = {row["project"]: row for row in repository_df.to_dict(orient="records")}

    for tooName in os.listdir(f"{CACHE_DIRECTORY}/history"):
        processed_count = 0
        skipped_count = 0

        for zip_file in Path(f"{CACHE_DIRECTORY}/history/{tooName}").rglob("*.tar.gz"):
            method_history_list = []
            repository_name = zip_file.name[:-len(".tar.gz")]
            if repository_name in repository_name_map:
                repository_url = repository_name_map[repository_name]["url"]
                repository_hash = repository_name_map[repository_name]["updated_hash"]
                with tarfile.open(zip_file, "r:gz") as tar:
                    for file in tar.getmembers():
                        if file.isfile() and file.name.endswith(".json"):
                            _, base_file = file.name.split("/", maxsplit=1)
                            file_content = tar.extractfile(file)
                            if file_content is not None:
                                try:
                                    history_json = json.load(file_content)
                                except Exception:
                                    logging.error(f"Error loading history json for {tooName} {file}")
                                    continue
                                change_history = extract_change_count(history_json)

                                method_url = util.convert_method_file_to_method_url(
                                    repository_url, repository_hash, base_file
                                )
                                method_history = {
                                    "url": method_url,
                                    "tool_name": tooName,
                                    "method_file": base_file
                                }
                                method_history.update(change_history)
                                method_history_list.append(method_history)
                method_file = util.format_method_list_file(DATA_DIRECTORY, repository_name)
                if os.path.exists(method_file):
                    method_list_df = pd.read_csv(method_file, keep_default_na=False, na_filter=False)
                    repository_change_history_file = f"{DATA_DIRECTORY}/history/{tooName}/{repository_name}.csv"
                    os.makedirs(os.path.dirname(repository_change_history_file), exist_ok=True)
                    pd.merge(method_list_df, pd.DataFrame(method_history_list), on="url", how="inner").to_csv(
                        repository_change_history_file, index=False
                    )
                    processed_count += 1
                else:
                    warnings.warn(f"Missing method history file for {tooName} {repository_name}")
                    skipped_count += 1
            else:
                skipped_count += 1

        print(f"generate_change summary [{tooName}]: processed={processed_count}, skipped={skipped_count}")


if __name__ == "__main__":
    main()

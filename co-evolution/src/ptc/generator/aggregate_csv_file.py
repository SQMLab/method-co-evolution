from mhc.config import *
import pandas as pd
from pathlib import Path


def aggregate_csv_files(input_dir: str, output_file_name: str):
    dfs = [pd.read_csv(file, keep_default_na=False, na_filter=False) for
           file in list(Path(input_dir).rglob("*.csv"))]
    dfs = [d for d in dfs if not d.empty]
    if dfs:
        df = pd.concat(dfs, ignore_index=True)
        os.makedirs(f"{DATA_DIRECTORY}/aggregate", exist_ok=True)
        df.to_csv(f"{DATA_DIRECTORY}/aggregate/{output_file_name}", index=False)


aggregate_csv_files(f"{DATA_DIRECTORY}/m2m-confidence", "m2m-confidence.csv")
t2p_strategy_dirs = [dir_name for dir_name in os.listdir(f"{DATA_DIRECTORY}/t2p-link") if
                     os.path.isdir(f"{DATA_DIRECTORY}/t2p-link/{dir_name}")]
for t2p_strategy in t2p_strategy_dirs:
    aggregate_csv_files(f"{DATA_DIRECTORY}/t2p-link/{t2p_strategy}",
                        f"t2p-link--{t2p_strategy}.csv")

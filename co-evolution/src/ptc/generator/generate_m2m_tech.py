from collections import defaultdict, deque

import pandas as pd
from pytctracer.techniques.levenshtein_distance import *
from pytctracer.techniques.longest_common_subsequence import *
from pytctracer.techniques.naming_conventions import *

import mhc.util as util
from mhc.config import *

# ---------------------------
# Config
# ---------------------------

MAX_EXPANSION_DEPTH = 5

FANOUT_DIR = f"{DATA_DIRECTORY}/fan-out"
METHOD_DIR = f"{DATA_DIRECTORY}/method"
T2P_CANDIDATE_DIR = f"{DATA_DIRECTORY}/t2p-candidate"
OUTPUT_DIR = f"{DATA_DIRECTORY}/m2m-tech"

os.makedirs(T2P_CANDIDATE_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------------------------
# Techniques
# ---------------------------

nc = NamingConventions()
ncc = NamingConventionsContains()
ld = LevenshteinDistance()
lcsUnit = LongestCommonSubsequenceUnit()
lcsBoth = LongestCommonSubsequenceUnit()

repository_df = pd.read_csv(f"{DATA_DIRECTORY}/repository/repository.csv")


# ---------------------------
# Confidence computation
# ---------------------------

def establish_confidence(row):
    test_name = row["from_name"].lower()
    production_name = row["to_name"].lower()

    return pd.Series({
        "tech_nc": nc._compute_nc_score(production_name, test_name),
        "tech_ncc": ncc._compute_nc_score(production_name, test_name),
        "tech_lcs_b": lcsBoth._compute_lcs_score(production_name, test_name),
        "tech_lcs_u": lcsUnit._compute_lcs_score(production_name, test_name),
        "tech_leven": ld._compute_levenshtein_score(production_name, test_name)
    })


# ---------------------------
# Main Processing
# ---------------------------

for _, repo in repository_df.iterrows():

    project = repo["project"]
    commit_hash = repo["updated_hash"]

    t2p_candidate_file = f"{T2P_CANDIDATE_DIR}/{project}.csv"
    method_file = f"{METHOD_DIR}/{project}.csv"

    if os.path.exists(t2p_candidate_file):
        print("Processing:", project)

        t2p_candidate_df = pd.read_csv(t2p_candidate_file, na_filter=False, keep_default_na=False)

        # ---------------------------
        # Apply Techniques
        # ---------------------------

        t2p_candidate_df[[
            "tech_nc",
            "tech_ncc",
            "tech_lcs_b",
            "tech_lcs_u",
            "tech_leven"
        ]] = t2p_candidate_df.apply(
            establish_confidence,
            axis=1
        ).round(2)

        t2p_candidate_df["tech_lc"] = (
                t2p_candidate_df.groupby("from_url").cumcount()
                == t2p_candidate_df.groupby("from_url")["from_url"].transform("size") - 1
        ).astype(int)

        t2p_candidate_df["tech_lcba"] = t2p_candidate_df["to_lcba"].astype(int)

        expanded_df = util.convert_float_int_columns_to_nullable_int(t2p_candidate_df)

        output_file = f"{OUTPUT_DIR}/{project}.csv"
        expanded_df.to_csv(output_file, index=False)

print("Finished.")

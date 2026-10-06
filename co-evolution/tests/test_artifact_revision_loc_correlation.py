from pathlib import Path
import sys
import unittest

import pandas as pd

SRC_DIRECTORY = Path(__file__).resolve().parents[1] / "src"
MHC_SRC_DIRECTORY = Path(__file__).resolve().parents[2] / "method-history-collector" / "src"
for directory in (SRC_DIRECTORY, MHC_SRC_DIRECTORY):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from ptc.generator.artifact_revision_loc_correlation import (
    correlation_rows,
    pooled_test_methods,
)


class TestArtifactRevisionLocCorrelation(unittest.TestCase):
    def test_pooled_test_methods_keeps_only_complete_test_method_rows(self):
        frame = pd.DataFrame(
            [
                {"method_kind": "test-case-method", "loc_init": "3", "ch_diff": "1"},
                {"method_kind": "test-case-method", "loc_init": "", "ch_diff": "2"},
                {"method_kind": "test-case-method", "loc_init": "5", "ch_diff": ""},
                {"method_kind": "main-code", "loc_init": "7", "ch_diff": "3"},
            ]
        )

        result = pooled_test_methods(frame)

        self.assertEqual([{"loc_init": 3.0, "ch_diff": 1.0}], result.to_dict(orient="records"))

    def test_correlation_rows_report_all_algorithms_and_p_values(self):
        frame = pd.DataFrame(
            [
                {"method_kind": "test-case-method", "loc_init": 1, "ch_diff": 1},
                {"method_kind": "test-case-method", "loc_init": 2, "ch_diff": 2},
                {"method_kind": "test-case-method", "loc_init": 3, "ch_diff": 3},
            ]
        )

        rows = correlation_rows(frame, tool="historyFinder")

        self.assertEqual(["kendall", "spearman", "pearson"], [row["correlation_algorithm"] for row in rows])
        self.assertTrue(all(row["correlation"] == 1.0 for row in rows))
        self.assertTrue(all(pd.notna(row["p_value"]) for row in rows))
        self.assertTrue(all(row["methods"] == 3 for row in rows))

    def test_constant_values_produce_missing_statistics(self):
        frame = pd.DataFrame(
            [
                {"method_kind": "test-case-method", "loc_init": 4, "ch_diff": 1},
                {"method_kind": "test-case-method", "loc_init": 4, "ch_diff": 2},
            ]
        )

        rows = correlation_rows(frame, tool="historyFinder")

        self.assertEqual(3, len(rows))
        self.assertTrue(all(pd.isna(row["correlation"]) for row in rows))
        self.assertTrue(all(pd.isna(row["p_value"]) for row in rows))


if __name__ == "__main__":
    unittest.main()

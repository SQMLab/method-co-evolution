from pathlib import Path
import sys
import tempfile
import unittest

import pandas as pd

SRC_DIRECTORY = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SRC_DIRECTORY))

from ptc.sample.t2p_ground_truth_agreement import (
    compare_directories,
    compare_project,
    main,
)


class TestT2PGroundTruthAgreement(unittest.TestCase):
    def rows(self):
        return [
            {
                "project": "demo",
                "from_url": "test://a",
                "to_url": "prod://1",
                "from_name": "testA",
                "to_name": "prod1",
                "label": "1",
                "tags": "left-tag",
                "notes": "left-note",
                "candidate": "1",
            },
            {
                "project": "demo",
                "from_url": "test://b",
                "to_url": "prod://2",
                "from_name": "testB",
                "to_name": "prod2",
                "label": "0",
                "tags": "",
                "notes": "",
                "candidate": "1",
            },
        ]

    def write_gt(self, directory: Path, project: str, rows: list[dict[str, str]]) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        csv_file = directory / f"{project}.csv"
        pd.DataFrame(rows).to_csv(csv_file, index=False)
        return csv_file

    def test_matching_labels_increase_agreement_and_kappa(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            left = self.write_gt(root / "left", "demo", self.rows())
            right = self.write_gt(root / "right", "demo", self.rows())

            disagreement_df, summary = compare_project("demo", left, right)

            self.assertTrue(disagreement_df.empty)
            self.assertEqual(2, summary["agreements"])
            self.assertEqual(0, summary["disagreements"])
            self.assertEqual(1.0, summary["percent_agreement"])
            self.assertEqual(1.0, summary["cohen_kappa"])

    def test_mismatched_labels_are_written_to_disagreement_rows(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            left = self.write_gt(root / "left", "demo", self.rows())
            right_rows = self.rows()
            right_rows[1]["label"] = "1"
            right_rows[1]["tags"] = "right-tag"
            right = self.write_gt(root / "right", "demo", right_rows)

            disagreement_df, summary = compare_project("demo", left, right)

            self.assertEqual(1, len(disagreement_df))
            self.assertEqual("label_mismatch", disagreement_df.iloc[0]["disagreement"])
            self.assertEqual("0", disagreement_df.iloc[0]["left_label"])
            self.assertEqual("1", disagreement_df.iloc[0]["right_label"])
            self.assertEqual("right-tag", disagreement_df.iloc[0]["right_tags"])
            self.assertEqual(1, summary["disagreements"])

    def test_only_left_and_only_right_pairs_count_as_disagreements(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            left = self.write_gt(root / "left", "demo", [self.rows()[0]])
            right_row = self.rows()[1]
            right = self.write_gt(root / "right", "demo", [right_row])

            disagreement_df, summary = compare_project("demo", left, right)

            self.assertEqual({"only_left", "only_right"}, set(disagreement_df["disagreement"]))
            self.assertEqual(0, summary["agreements"])
            self.assertEqual(2, summary["disagreements"])
            self.assertEqual(1, summary["only_left"])
            self.assertEqual(1, summary["only_right"])

    def test_blank_labels_count_as_disagreements_but_are_ignored_by_kappa(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            left_rows = self.rows()
            right_rows = self.rows()
            right_rows[1]["label"] = ""
            left = self.write_gt(root / "left", "demo", left_rows)
            right = self.write_gt(root / "right", "demo", right_rows)

            disagreement_df, summary = compare_project("demo", left, right)

            self.assertEqual(1, len(disagreement_df))
            self.assertEqual("unlabeled_or_invalid", disagreement_df.iloc[0]["disagreement"])
            self.assertEqual(1, summary["agreements"])
            self.assertEqual(1, summary["disagreements"])
            self.assertEqual(1, summary["unlabeled_or_invalid"])
            self.assertEqual(0.5, summary["percent_agreement"])
            self.assertEqual(1.0, summary["cohen_kappa"])

    def test_conflicting_duplicate_labels_fail_validation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            duplicate_rows = [self.rows()[0], {**self.rows()[0], "label": "0"}]
            left = self.write_gt(root / "left", "demo", duplicate_rows)
            right = self.write_gt(root / "right", "demo", [self.rows()[0]])

            with self.assertRaisesRegex(ValueError, "conflicting duplicate labels"):
                compare_project("demo", left, right)

    def test_compare_directories_filters_projects_and_adds_total(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            left_dir = root / "left"
            right_dir = root / "right"
            self.write_gt(left_dir, "alpha", self.rows())
            self.write_gt(right_dir, "alpha", self.rows())
            self.write_gt(left_dir, "beta", self.rows())
            self.write_gt(right_dir, "beta", [{**row, "label": "1"} for row in self.rows()])

            disagreements, summary_df = compare_directories(left_dir, right_dir, ["beta"])

            self.assertEqual(["beta"], list(disagreements))
            self.assertEqual(["beta", "total"], summary_df["project"].tolist())
            self.assertEqual(2, int(summary_df.iloc[-1]["union_pairs"]))
            self.assertEqual(1, int(summary_df.iloc[-1]["agreements"]))

    def test_main_writes_default_outputs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workspace = root / "workspace"
            left_dir = root / "data" / "t2plinker" / "t2p-ground-truth"
            right_dir = root / "data" / "t2plinker" / "t2p-ground-truth-2"
            self.write_gt(left_dir, "demo", self.rows())
            self.write_gt(right_dir, "demo", [{**row, "label": "1"} for row in self.rows()])

            result = main(
                [
                    "--project-directory",
                    str(root),
                    "--workspace-directory",
                    str(workspace),
                    "--experiment-name",
                    "main",
                ]
            )

            self.assertEqual(0, result)
            self.assertTrue(
                (workspace / "experiment" / "main" / "t2p-ground-truth-disagreement" / "demo.csv").exists()
            )
            summary_file = workspace / "experiment" / "main" / "aggregate" / "agreement-summary.csv"
            self.assertTrue(summary_file.exists())
            summary_df = pd.read_csv(summary_file, keep_default_na=False, na_filter=False)
            self.assertEqual(["demo", "total"], summary_df["project"].tolist())


if __name__ == "__main__":
    unittest.main()

from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

SRC_DIRECTORY = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SRC_DIRECTORY))

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None

from ptc.sample import ground_truth_sample


@unittest.skipIf(pd is None, "pandas is required for ground truth sample tests")
class TestGroundTruthSample(unittest.TestCase):
    def test_project_index_selects_repository_rows(self):
        projects = ["commons-io", "commons-lang", "gson"]

        self.assertEqual(["commons-lang"], ground_truth_sample._parse_project_index("1", projects))
        self.assertEqual(["commons-lang", "gson"], ground_truth_sample._parse_project_index("1:", projects))
        self.assertEqual(["commons-io", "commons-lang"], ground_truth_sample._parse_project_index(":2", projects))
        self.assertEqual(["gson"], ground_truth_sample._parse_project_index("-1", projects))

    def test_regenerate_preserves_labels_and_fills_sample_from_fresh_candidates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            candidate_dir, method_dir, working_dir, output_dir = self._make_dirs(root)
            self._write_project_inputs(candidate_dir, method_dir, project="demo", test_count=3)
            pd.DataFrame(
                [
                    {
                        "project": "demo",
                        "from_name": "testA",
                        "to_name": "prod1",
                        "from_url": "test://A",
                        "to_url": "prod://1",
                        "label": "1",
                        "tags": "needs-check",
                        "notes": "keep this",
                    }
                ]
            ).to_csv(working_dir / "demo.csv", index=False)

            with self._patch_input_dirs(candidate_dir, method_dir):
                stats = ground_truth_sample.regenerate_project(
                    project="demo",
                    sample_count_per_project=2,
                    working_dir=working_dir,
                    output_dir=output_dir,
                )

            result = pd.read_csv(output_dir / "demo.csv", keep_default_na=False, na_filter=False)
            self.assertIsNotNone(stats)
            self.assertEqual(1, stats.reused_test_methods)
            self.assertEqual(1, stats.added_test_methods)
            self.assertEqual(2, result["from_url"].nunique())
            preserved = result[(result["from_url"] == "test://A") & (result["to_url"] == "prod://1")].iloc[0]
            self.assertEqual("1", str(preserved["label"]))
            self.assertEqual("needs-check", preserved["tags"])
            self.assertEqual("keep this", preserved["notes"])

    def test_regenerate_without_working_csv_samples_requested_count(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            candidate_dir, method_dir, working_dir, output_dir = self._make_dirs(root)
            self._write_project_inputs(candidate_dir, method_dir, project="demo", test_count=3)

            with self._patch_input_dirs(candidate_dir, method_dir):
                stats = ground_truth_sample.regenerate_project(
                    project="demo",
                    sample_count_per_project=2,
                    working_dir=working_dir,
                    output_dir=output_dir,
                )

            result = pd.read_csv(output_dir / "demo.csv", keep_default_na=False, na_filter=False)
            self.assertEqual(0, stats.reused_test_methods)
            self.assertEqual(2, stats.added_test_methods)
            self.assertEqual(2, result["from_url"].nunique())

    def test_regenerate_keeps_over_sample_existing_methods(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            candidate_dir, method_dir, working_dir, output_dir = self._make_dirs(root)
            self._write_project_inputs(candidate_dir, method_dir, project="demo", test_count=3)
            pd.DataFrame(
                [
                    {"project": "demo", "from_url": "test://A", "to_url": "prod://1", "label": "1"},
                    {"project": "demo", "from_url": "test://B", "to_url": "prod://1", "label": "0"},
                    {"project": "demo", "from_url": "test://C", "to_url": "prod://1", "label": "1"},
                ]
            ).to_csv(working_dir / "demo.csv", index=False)

            with self._patch_input_dirs(candidate_dir, method_dir):
                stats = ground_truth_sample.regenerate_project(
                    project="demo",
                    sample_count_per_project=2,
                    working_dir=working_dir,
                    output_dir=output_dir,
                )

            result = pd.read_csv(output_dir / "demo.csv", keep_default_na=False, na_filter=False)
            self.assertEqual(3, stats.reused_test_methods)
            self.assertEqual(0, stats.added_test_methods)
            self.assertEqual(3, result["from_url"].nunique())

    def test_regenerate_overwrites_existing_output_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            candidate_dir, method_dir, working_dir, output_dir = self._make_dirs(root)
            self._write_project_inputs(candidate_dir, method_dir, project="demo", test_count=1)
            (output_dir / "demo.csv").write_text("old,column\nstale,value\n", encoding="utf-8")

            with self._patch_input_dirs(candidate_dir, method_dir):
                ground_truth_sample.regenerate_project(
                    project="demo",
                    sample_count_per_project=1,
                    working_dir=working_dir,
                    output_dir=output_dir,
                )

            result = pd.read_csv(output_dir / "demo.csv", keep_default_na=False, na_filter=False)
            self.assertEqual(ground_truth_sample.GROUND_TRUTH_COLUMNS, result.columns.tolist())
            self.assertEqual(["test://A"], result["from_url"].drop_duplicates().tolist())

    def _make_dirs(self, root: Path) -> tuple[Path, Path, Path, Path]:
        candidate_dir = root / "t2p-candidate-expanded"
        method_dir = root / "method"
        working_dir = root / "working"
        output_dir = root / "output"
        for directory in (candidate_dir, method_dir, working_dir, output_dir):
            directory.mkdir(parents=True)
        return candidate_dir, method_dir, working_dir, output_dir

    def _patch_input_dirs(self, candidate_dir: Path, method_dir: Path):
        return mock.patch.multiple(
            ground_truth_sample,
            T2P_CANDIDATE_DIR=candidate_dir,
            METHOD_DIR=method_dir,
        )

    def _write_project_inputs(
        self,
        candidate_dir: Path,
        method_dir: Path,
        *,
        project: str,
        test_count: int,
    ) -> None:
        test_urls = [f"test://{chr(ord('A') + index)}" for index in range(test_count)]
        candidate_rows = []
        method_rows = [
            {"url": "prod://1", "artifact": "production"},
            {"url": "test-helper://1", "artifact": "#test-code #test-utility"},
        ]
        for index, test_url in enumerate(test_urls):
            method_rows.append({"url": test_url, "artifact": "#test-code #test-unit #test-method"})
            candidate_rows.extend(
                [
                    {
                        "project": project,
                        "from_name": f"test{chr(ord('A') + index)}",
                        "to_name": "prod1",
                        "from_url": test_url,
                        "to_url": "prod://1",
                        "from_fqs": f"DemoTest.test{index}()",
                        "from_tctracer_fqs": f"DemoTest.test{index}()",
                        "from_testlinker_fqs": f"DemoTest.test{index}()",
                        "to_fqs": "Demo.prod1()",
                        "to_tctracer_fqs": "Demo.prod1()",
                        "to_testlinker_fqs": "Demo.prod1()",
                        "to_call_depth": 1,
                    },
                    {
                        "project": project,
                        "from_name": f"test{chr(ord('A') + index)}",
                        "to_name": "helper",
                        "from_url": test_url,
                        "to_url": "test-helper://1",
                        "from_fqs": f"DemoTest.test{index}()",
                        "from_tctracer_fqs": f"DemoTest.test{index}()",
                        "from_testlinker_fqs": f"DemoTest.test{index}()",
                        "to_fqs": "DemoTest.helper()",
                        "to_tctracer_fqs": "DemoTest.helper()",
                        "to_testlinker_fqs": "DemoTest.helper()",
                        "to_call_depth": 1,
                    },
                ]
            )

        pd.DataFrame(candidate_rows).to_csv(candidate_dir / f"{project}.csv", index=False)
        pd.DataFrame(method_rows).to_csv(method_dir / f"{project}.csv", index=False)


if __name__ == "__main__":
    unittest.main()

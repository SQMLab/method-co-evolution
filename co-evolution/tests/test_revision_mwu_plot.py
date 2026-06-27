from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import warnings

SRC_DIRECTORY = Path(__file__).resolve().parents[1] / "src"
MHC_SRC_DIRECTORY = Path(__file__).resolve().parents[2] / "method-history-collector" / "src"
for directory in (SRC_DIRECTORY, MHC_SRC_DIRECTORY):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None

from ptc.plot.artifact_revision_mww_table import main


@unittest.skipIf(pd is None, "pandas is required for revision_mwu plot tests")
class TestRevisionMwuPlot(unittest.TestCase):
    def test_generates_one_diff_table_per_tool(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            experiment_dir = self.create_experiment(tmpdir)
            self.write_revision_mwu_csv(experiment_dir)
            output_directory = Path(tmpdir) / "paper-figure"

            with warnings.catch_warnings(record=True) as caught_warnings:
                warnings.simplefilter("always")
                main(
                    [
                        "--workspace-directory",
                        tmpdir,
                        "--experiment-name",
                        "demo",
                        "--tools",
                        "codeShovel,historyFinder",
                        "--output-directory",
                        str(output_directory),
                    ]
                )

            first_build_dir = output_directory / "build" / "artifact-revision-mww--historyFinder"
            second_build_dir = output_directory / "build" / "artifact-revision-mww--codeShovel"
            first_tex = first_build_dir / "artifact-revision-mww--historyFinder.tex"
            second_tex = second_build_dir / "artifact-revision-mww--codeShovel.tex"
            self.assertTrue(first_tex.exists())
            self.assertTrue(second_tex.exists())
            self.assertFalse((output_directory / "artifact-revision-mww--historyFinder.tex").exists())
            self.assertFalse((output_directory / "artifact-revision-mww--historyFinder.aux").exists())
            self.assertFalse((output_directory / "artifact-revision-mww--historyFinder.log").exists())

            first_text = first_tex.read_text(encoding="utf-8")
            self.assertIn("projectA", first_text)
            self.assertIn("all", first_text)
            self.assertNotIn("projectOnlyAllChange", first_text)
            self.assertIn(r"\textbf{$+$}~(1~project(s))", first_text)
            self.assertIn(r"\textbf{$-$}~(1~project(s))", first_text)
            self.assertIn(
                r"The pooled all-project comparison reports $p < 0.05$, Cliff's~$\delta=-0.10$, "
                r"indicating a negligible overall difference with test methods revised more frequently overall.",
                first_text,
            )
            self.assertIn(r"all & 0.00 & -0.10 & - & x &  &  &  \\", first_text)

            if shutil.which("pdflatex") is None:
                self.assertTrue(any("pdflatex not found" in str(warning.message) for warning in caught_warnings))
            else:
                self.assertTrue((output_directory / "artifact-revision-mww--historyFinder.pdf").exists())
                self.assertTrue((output_directory / "artifact-revision-mww--codeShovel.pdf").exists())
                self.assertTrue((first_build_dir / "artifact-revision-mww--historyFinder.pdf").exists())
                self.assertTrue((first_build_dir / "artifact-revision-mww--historyFinder.aux").exists())
                self.assertTrue((first_build_dir / "artifact-revision-mww--historyFinder.log").exists())

    def create_experiment(self, workspace_dir: str) -> Path:
        experiment_dir = Path(workspace_dir) / "experiment" / "demo"
        (experiment_dir / "aggregate").mkdir(parents=True)
        return experiment_dir

    def write_revision_mwu_csv(self, experiment_dir: Path) -> None:
        rows = [
            {
                "project": "projectA",
                "tool": "historyFinder",
                "change": "diff",
                "size": 6,
                "main_size": 3,
                "test_size": 3,
                "mww_u1": 9,
                "mww_u2": 0,
                "mww_p": 0.1,
                "d_value": 1,
                "d_sign": "+",
                "effect_size": "large",
                "N": "",
                "S": "",
                "M": "",
                "L": "x",
            },
            {
                "project": "all",
                "tool": "historyFinder",
                "change": "diff",
                "size": 6,
                "main_size": 3,
                "test_size": 3,
                "mww_u1": 9,
                "mww_u2": 0,
                "mww_p": 0.0,
                "d_value": -0.1,
                "d_sign": "-",
                "effect_size": "negligible",
                "N": "x",
                "S": "",
                "M": "",
                "L": "",
            },
            {
                "project": "projectC",
                "tool": "historyFinder",
                "change": "diff",
                "size": 6,
                "main_size": 3,
                "test_size": 3,
                "mww_u1": 0,
                "mww_u2": 9,
                "mww_p": 0.3,
                "d_value": -0.5,
                "d_sign": "-",
                "effect_size": "large",
                "N": "",
                "S": "",
                "M": "",
                "L": "x",
            },
            {
                "project": "projectOnlyAllChange",
                "tool": "historyFinder",
                "change": "all",
                "size": 6,
                "main_size": 3,
                "test_size": 3,
                "mww_u1": 9,
                "mww_u2": 0,
                "mww_p": 0.1,
                "d_value": 1,
                "d_sign": "+",
                "effect_size": "large",
                "N": "",
                "S": "",
                "M": "",
                "L": "x",
            },
            {
                "project": "projectB",
                "tool": "codeShovel",
                "change": "diff",
                "size": 6,
                "main_size": 3,
                "test_size": 3,
                "mww_u1": 9,
                "mww_u2": 0,
                "mww_p": 0.2,
                "d_value": 0.8,
                "d_sign": "+",
                "effect_size": "large",
                "N": "",
                "S": "",
                "M": "",
                "L": "x",
            },
        ]
        pd.DataFrame(rows).to_csv(experiment_dir / "aggregate" / "artifact-revision-mww.csv", index=False)


if __name__ == "__main__":
    unittest.main()

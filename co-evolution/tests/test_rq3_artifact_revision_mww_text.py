from pathlib import Path
from contextlib import redirect_stdout
import io
import sys
import tempfile
import unittest

SRC_DIRECTORY = Path(__file__).resolve().parents[1] / "src"
MHC_SRC_DIRECTORY = Path(__file__).resolve().parents[2] / "method-history-collector" / "src"
for directory in (SRC_DIRECTORY, MHC_SRC_DIRECTORY):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None

from ptc.generator.rq3_artifact_revision_mww_text import main, render_summary_text


@unittest.skipIf(pd is None, "pandas is required for RQ3 MWU text tests")
class TestRQ3ArtifactRevisionMwwText(unittest.TestCase):
    def test_render_summary_uses_all_row_only_for_overall_result(self):
        df = pd.DataFrame(
            [
                self.row("all", 0.0, -0.1, "-", "negligible"),
                self.row("testNegligible", 0.01, -0.1, "-", "negligible"),
                self.row("testSmall", 0.03, -0.2, "-", "small"),
                self.row("testMedium", 0.04, -0.4, "-", "medium"),
                self.row("testLarge", 0.05, -0.5, "-", "large"),
                self.row("testNotSig", 0.20, -0.2, "-", "small"),
                self.row("prodNegligible", 0.01, 0.1, "+", "negligible"),
                self.row("prodSmall", 0.03, 0.2, "+", "small"),
                self.row("prodMedium", 0.04, 0.4, "+", "medium"),
                self.row("prodLarge", 0.05, 0.5, "+", "large"),
                self.row("prodNotSig", 0.30, 0.2, "+", "small"),
            ]
        )

        text = render_summary_text(df)

        self.assertIn(r"statistically significant ($p < 0.05$)", text)
        self.assertIn(r"negligible effect size (Cliff's~$\delta=-0.10$)", text)
        self.assertIn("test methods revised more frequently overall", text)
        self.assertIn("test methods were revised more frequently than production methods in 5 projects", text)
        self.assertIn("statistically significant differences in 4 projects", text)
        self.assertIn("negligible in 25.0\\%, small in 25.0\\%, medium in 25.0\\%, and large in 25.0\\%", text)
        self.assertIn("production methods were revised more frequently than test methods in 5 projects", text)
        self.assertNotIn("in 6 projects", text)

    def test_main_prints_summary_without_writing_latex_fragment(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            experiment_dir = root / "experiment" / "demo"
            aggregate_dir = experiment_dir / "aggregate"
            aggregate_dir.mkdir(parents=True)
            pd.DataFrame(
                [
                    {
                        **self.row("all", 0.0, -0.1, "-", "negligible"),
                        "tool": "historyFinder",
                        "change": "diff",
                    },
                    {
                        **self.row("projectA", 0.01, -0.2, "-", "small"),
                        "tool": "historyFinder",
                        "change": "diff",
                    },
                    {
                        **self.row("projectB", 0.30, 0.2, "+", "small"),
                        "tool": "historyFinder",
                        "change": "diff",
                    },
                    {
                        **self.row("projectC", 0.01, -0.2, "-", "small"),
                        "tool": "codeShovel",
                        "change": "diff",
                    },
                ]
            ).to_csv(aggregate_dir / "artifact-revision-mww.csv", index=False)
            output_directory = root / "paper" / "rq3"

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                main(
                    [
                        "--project-directory",
                        str(root),
                        "--workspace-directory",
                        str(root),
                        "--experiment-name",
                        "demo",
                        "--output-directory",
                        str(output_directory),
                    ]
                )

            text = stdout.getvalue()
            output_file = output_directory / "rq3-artifact-revision-mww-text.tex"
            self.assertFalse(output_file.exists())
            self.assertIn("test methods were revised more frequently than production methods in 1 project", text)
            self.assertIn("production methods were revised more frequently than test methods in 1 project", text)

    def row(self, project: str, p_value: float, d_value: float, sign: str, effect_size: str) -> dict:
        return {
            "project": project,
            "mww_p": p_value,
            "d_value": d_value,
            "d_sign": sign,
            "effect_size": effect_size,
        }


if __name__ == "__main__":
    unittest.main()

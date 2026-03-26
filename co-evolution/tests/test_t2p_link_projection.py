from pathlib import Path
import sys
import tempfile
import unittest

SRC_DIRECTORY = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SRC_DIRECTORY))

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None

from ptc.llm.t2p_link_projection import project_t2p_links


@unittest.skipIf(pd is None, "pandas is required for projection tests")
class TestT2pLinkProjection(unittest.TestCase):
    def test_project_t2p_links_maps_selected_methods(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            candidate_file = tmpdir_path / "demo-candidate.csv"
            llm_run_file = tmpdir_path / "demo-run.csv"
            output_file = tmpdir_path / "demo-link.csv"

            pd.DataFrame(
                [
                    {
                        "project": "demo",
                        "from_name": "testSaveItem",
                        "to_name": "saveItem",
                        "from_url": "f1",
                        "to_url": "t1",
                    },
                    {
                        "project": "demo",
                        "from_name": "testSaveItem",
                        "to_name": "deleteItem",
                        "from_url": "f1",
                        "to_url": "t2",
                    },
                ]
            ).to_csv(candidate_file, index=False)

            pd.DataFrame(
                [
                    {
                        "name": "testSaveItem",
                        "fqs": "org.example.Test.testSaveItem()",
                        "url": "f1",
                        "prompt_text": "prompt",
                        "messages_json": "[]",
                        "metadata_json": "{}",
                        "output_raw": "raw",
                        "output_json": (
                            '{"methods":[{"name":"saveItem","confidence":0.95,"rationale":"Direct call"}],'
                            '"overall_rationale":"One clear match."}'
                        ),
                        "error": "",
                        "created_at": "2026-03-26T00:00:00+00:00",
                        "updated_at": "2026-03-26T00:00:00+00:00",
                    }
                ]
            ).to_csv(llm_run_file, index=False)

            projected_df = project_t2p_links(
                candidate_file=candidate_file,
                llm_run_file=llm_run_file,
                output_file=output_file,
            )

            self.assertEqual([1, 0], projected_df["label_pred"].tolist())
            self.assertEqual(0.95, projected_df.loc[0, "confidence"])
            self.assertEqual("Direct call", projected_df.loc[0, "rationale"])
            self.assertEqual("", projected_df.loc[1, "rationale"])
            self.assertTrue(output_file.exists())


if __name__ == "__main__":
    unittest.main()

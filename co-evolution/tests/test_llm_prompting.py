from pathlib import Path
import sys
import unittest

SRC_DIRECTORY = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SRC_DIRECTORY))

from ptc.llm.prompting import JsonPredictionParser, MethodLinkingPromptFactory
from ptc.llm.models import PromptInput

try:
    import pandas as pd
except ImportError:  # pragma: no cover - local shell may not have pandas installed
    pd = None


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FAN_OUT_FILE = REPOSITORY_ROOT / ".white" / "data" / "fan-out" / "commons-io.csv"
FAN_IN_FILE = REPOSITORY_ROOT / ".white" / "data" / "fan-in" / "commons-io.csv"

T2P_SOURCE_URL = (
    "https://github.com/apache/commons-io/blob/"
    "4077158829de92987367d3149e4ba71356bb5390/src/test/java/"
    "org/apache/commons/io/ByteOrderMarkTestCase.java#L45"
)
P2T_SOURCE_URL = (
    "https://github.com/apache/commons-io/blob/"
    "4077158829de92987367d3149e4ba71356bb5390/src/main/java/"
    "org/apache/commons/io/FileUtils.java#L416"
)


def _load_group(csv_file: Path, group_column: str, group_value: str):
    if pd is None:
        raise unittest.SkipTest("pandas is required for dataframe prompt tests")
    if not csv_file.exists():
        raise unittest.SkipTest(f"Required fixture CSV is missing: {csv_file}")

    frame = pd.read_csv(csv_file, keep_default_na=False, na_filter=False)
    group = frame[frame[group_column] == group_value].copy()
    if group.empty:
        raise unittest.SkipTest(f"Could not find fixture group {group_value} in {csv_file}")
    return group


class TestMethodLinkPromptFactory(unittest.TestCase):
    def test_t2p_prompt_contains_real_commons_io_methods(self):
        case_df = _load_group(FAN_OUT_FILE, "from_url", T2P_SOURCE_URL)

        prompt = MethodLinkingPromptFactory().build_prompt(case_df, "t2p")

        self.assertEqual(2, len(prompt.messages))
        self.assertEqual("system", prompt.messages[0].role)
        self.assertEqual("user", prompt.messages[1].role)
        self.assertIn("expert in identifying which production methods are being tested", prompt.prompt_text.lower())
        self.assertIn(
            "Fully qualified signature (FQS) of test method: "
            "org.apache.commons.io.ByteOrderMarkTestCase.charsetName()",
            prompt.prompt_text,
        )
        self.assertIn("Candidate production methods called by the test method:", prompt.prompt_text)
        self.assertIn("c1: org.apache.commons.io.ByteOrderMark.getCharsetName()", prompt.prompt_text)
        self.assertEqual("json_schema", prompt.response_format["type"])
        self.assertEqual("method_link_prediction", prompt.response_format["name"])

    def test_t2p_conventional_prompt_requests_labeled_output(self):
        case_df = _load_group(FAN_OUT_FILE, "from_url", T2P_SOURCE_URL)

        prompt = MethodLinkingPromptFactory().build_prompt(case_df, "t2p", prompt_format="text")

        self.assertIsNone(prompt.response_format)
        self.assertIn("METHOD: <exact candidate method from the list above or NONE>", prompt.prompt_text)
        self.assertIn("CONFIDENCE: <confidence between 0 and 1>", prompt.prompt_text)
        self.assertIn("RATIONALE: <short explanation>", prompt.prompt_text)
        self.assertIn("Start immediately with METHOD:", prompt.prompt_text)
        self.assertIn("Do not include analysis", prompt.prompt_text)
        self.assertNotIn("c1:", prompt.prompt_text)

    def test_p2t_prompt_contains_real_commons_io_methods(self):
        case_df = _load_group(FAN_IN_FILE, "to_url", P2T_SOURCE_URL)

        prompt = MethodLinkingPromptFactory().build_prompt(case_df, "p2t")

        self.assertEqual(2, len(prompt.messages))
        self.assertIn("expert in finding the test methods that call a production method", prompt.prompt_text.lower())
        self.assertIn(
            "Fully qualified signature (FQS) of production method: "
            "org.apache.commons.io.FileUtils.byteCountToDisplaySize(long)",
            prompt.prompt_text,
        )
        self.assertIn("Candidate test methods that call this production method:", prompt.prompt_text)
        self.assertIn(
            "c1: org.apache.commons.io.FileUtilsTestCase.testByteCountToDisplaySizeBigInteger()",
            prompt.prompt_text,
        )
        self.assertIn(
            "c2: org.apache.commons.io.FileUtilsTestCase.testByteCountToDisplaySizeLong()",
            prompt.prompt_text,
        )
        self.assertEqual("json_schema", prompt.response_format["type"])


class TestJsonPredictionParser(unittest.TestCase):
    def test_parse_prediction_maps_candidate_id_and_confidence_from_real_prompt(self):
        case_df = _load_group(FAN_OUT_FILE, "from_url", T2P_SOURCE_URL)
        prompt_input = MethodLinkingPromptFactory().build_prompt(case_df, "t2p")

        prediction = JsonPredictionParser().parse(
            prompt_input,
            (
                '{"candidate_ids":["c1"],'
                '"confidence":0.93,"rationale":"Real commons-io example"}'
            ),
        )

        self.assertEqual("match", prediction.label)
        self.assertEqual(["c1"], prediction.selected_candidate_ids)
        self.assertEqual([0.93], prediction.selected_candidate_confidences)
        self.assertEqual(
            ["org.apache.commons.io.ByteOrderMark.getCharsetName()"],
            prediction.selected_candidate_sigs,
        )
        self.assertEqual(
            [
                "https://github.com/apache/commons-io/blob/"
                "4077158829de92987367d3149e4ba71356bb5390/src/main/java/"
                "org/apache/commons/io/ByteOrderMark.java#L93"
            ],
            prediction.selected_candidate_urls,
        )
        self.assertAlmostEqual(0.93, prediction.confidence)

    def test_parse_prediction_falls_back_to_none_when_model_returns_non_json_text(self):
        case_df = _load_group(FAN_OUT_FILE, "from_url", T2P_SOURCE_URL)
        prompt_input = MethodLinkingPromptFactory().build_prompt(case_df, "t2p")

        prediction = JsonPredictionParser().parse(
            prompt_input,
            "The model repeated the prompt and never returned JSON.",
        )

        self.assertEqual("none", prediction.label)
        self.assertEqual([], prediction.selected_candidate_ids)
        self.assertIn("did not return a JSON object", prediction.rationale)

    def test_placeholder_schema_payload_is_not_treated_as_prediction(self):
        placeholder_payload = {
            "candidate_ids": [],
            "confidence": 0.0,
            "rationale": "short explanation",
        }

        self.assertFalse(JsonPredictionParser._looks_like_prediction_payload(placeholder_payload))

    def test_parse_prediction_accepts_candidate_ids_without_label(self):
        case_df = _load_group(FAN_OUT_FILE, "from_url", T2P_SOURCE_URL)
        prompt_input = MethodLinkingPromptFactory().build_prompt(case_df, "t2p")

        prediction = JsonPredictionParser().parse(
            prompt_input,
            (
                '{"candidate_ids":["c1","c2"],'
                '"confidence":0.0,"rationale":"Both c1 and c2 are used for testing ByteOrderMark equals()."}'
            ),
        )

        self.assertEqual("match", prediction.label)
        self.assertEqual(["c1", "c2"], prediction.selected_candidate_ids)

    def test_parse_prediction_accepts_raw_json_list_of_candidate_ids(self):
        case_df = _load_group(FAN_OUT_FILE, "from_url", T2P_SOURCE_URL)
        prompt_input = MethodLinkingPromptFactory().build_prompt(case_df, "t2p")

        prediction = JsonPredictionParser().parse(prompt_input, '["c1","c2"]')

        self.assertEqual("match", prediction.label)
        self.assertEqual(["c1", "c2"], prediction.selected_candidate_ids)

    def test_parse_prediction_accepts_repeated_method_blocks(self):
        case_df = _load_group(FAN_IN_FILE, "to_url", P2T_SOURCE_URL)
        prompt_input = MethodLinkingPromptFactory().build_prompt(case_df, "p2t", prompt_format="text")
        first_candidate = prompt_input.candidate_lookup["c1"]["fqs"]
        second_candidate = prompt_input.candidate_lookup["c2"]["fqs"]

        prediction = JsonPredictionParser().parse(
            prompt_input,
            (
                f"METHOD: {first_candidate}\n"
                "CONFIDENCE: 0.75\n"
                "RATIONALE: conventional output for the first method\n"
                f"METHOD: {second_candidate}\n"
                "CONFIDENCE: 0.60\n"
                "RATIONALE: conventional output for the second method"
            ),
        )

        self.assertEqual("match", prediction.label)
        self.assertEqual(["c1", "c2"], prediction.selected_candidate_ids)
        self.assertAlmostEqual(0.75, prediction.confidence)
        self.assertIn("first method", prediction.rationale)
        self.assertIn("second method", prediction.rationale)

    def test_parse_prediction_accepts_method_none_for_no_match(self):
        case_df = _load_group(FAN_OUT_FILE, "from_url", T2P_SOURCE_URL)
        prompt_input = MethodLinkingPromptFactory().build_prompt(case_df, "t2p", prompt_format="text")

        prediction = JsonPredictionParser().parse(
            prompt_input,
            "METHOD: NONE\nCONFIDENCE: 0.20\nRATIONALE: none of the listed methods are under test",
        )

        self.assertEqual("none", prediction.label)
        self.assertEqual([], prediction.selected_candidate_ids)
        self.assertAlmostEqual(0.20, prediction.confidence)

    def test_parse_prediction_ignores_preamble_and_resolves_unique_truncated_method(self):
        case_df = _load_group(FAN_OUT_FILE, "from_url", T2P_SOURCE_URL)
        prompt_input = MethodLinkingPromptFactory().build_prompt(case_df, "t2p", prompt_format="text")
        first_candidate = prompt_input.candidate_lookup["c1"]["fqs"]
        truncated_candidate = first_candidate.split("(", 1)[0] + "("

        prediction = JsonPredictionParser().parse(
            prompt_input,
            (
                "We need to determine which production method is under test.\n"
                "The test likely focuses on the first candidate.\n\n"
                f"METHOD: {truncated_candidate}\n"
                "CONFIDENCE: 0.88\n"
                "RATIONALE: The test name and assertions point to this candidate."
            ),
        )

        self.assertEqual("match", prediction.label)
        self.assertEqual(["c1"], prediction.selected_candidate_ids)
        self.assertAlmostEqual(0.88, prediction.confidence)

    def test_parse_prediction_accepts_inline_method_confidence_and_rationale(self):
        prompt_input = PromptInput(
            id="dirwalker-case",
            fqs="org.apache.commons.io.DirectoryWalkerTestCase.testMissingStartDirectory()",
            url="https://example/test#L1",
            prompt_text="",
            candidate_lookup={
                "c1": {
                    "fqs": "org.apache.commons.io.DirectoryWalker.walk(File, Collection)",
                    "sig": "org.apache.commons.io.DirectoryWalker.walk(File, Collection)",
                    "url": "https://example/prod#L10",
                }
            },
        )

        prediction = JsonPredictionParser().parse(
            prompt_input,
            (
                "We need to locate DirectoryWalkerTestCase in Apache Commons IO. "
                "The testMissingStartDirectory likely tests that the walk method throws for a missing directory. "
                "So we should output METHOD: org.apache.commons.io.DirectoryWalker.walk(File, Collection). "
                "Confidence high, maybe 0.99. "
                "Rationale: testMissingStartDirectory calls DirectoryWalker.walk with a missing start directory and expects exception."
            ),
        )

        self.assertEqual("match", prediction.label)
        self.assertEqual(["c1"], prediction.selected_candidate_ids)
        self.assertAlmostEqual(0.99, prediction.confidence)
        self.assertIn("missing start directory", prediction.rationale)


if __name__ == "__main__":
    unittest.main()

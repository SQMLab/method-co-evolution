from __future__ import annotations

import csv
from io import BytesIO
from pathlib import Path
import shutil
import sys
import unittest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PTC_SRC_DIRECTORY = REPOSITORY_ROOT / "co-evolution" / "src"
if str(PTC_SRC_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(PTC_SRC_DIRECTORY))

from ptc.history_viewer.app import (
    change_type_chip_class,
    create_app,
    format_commit_datetime,
    parse_unified_diff,
    render_change_chip,
    render_diff_html,
    truncate_display_text,
)
from ptc.history_viewer.repository import HistoryRepository, parse_commit_datetime, parse_method_url


CACHE_DIRECTORY = REPOSITORY_ROOT / ".cache"
DATA_DIRECTORY = CACHE_DIRECTORY / "data"
SAMPLE_CSV = DATA_DIRECTORY / "t2p-change-sample" / "historyFinder" / "omc--nc--ncc" / "cucumber-jvm.csv"
SAMPLE_DIR = DATA_DIRECTORY / "t2p-change-sample" / "historyFinder" / "omc--nc--ncc"
HF_DIRECT_FILE = CACHE_DIRECTORY / "history" / "historyFinder" / "auto" / "value" / "src" / "test" / "java" / "com" / "google" / "auto" / "value" / "extension" / "toprettystring" / "ToPrettyStringTest--toPrettyString--940.json"


class TestHistoryViewer(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = HistoryRepository(cache_directory=CACHE_DIRECTORY, data_directory=DATA_DIRECTORY)

    def test_parse_method_url_extracts_project_path_and_line(self) -> None:
        parsed = parse_method_url(
            "https://github.com/cucumber/cucumber-jvm/blob/4d9dd9304fe05e15c445c6f3b4d0e364d7c70223/"
            "cucumber-core/src/test/java/io/cucumber/core/plugin/UTF8PrintWriterTest.java#L17"
        )

        self.assertEqual("cucumber-jvm", parsed.project)
        self.assertEqual("cucumber-core/src/test/java/io/cucumber/core/plugin/UTF8PrintWriterTest.java", parsed.file_path)
        self.assertEqual(17, parsed.line)

    def test_format_commit_datetime_uses_readable_24_hour_output(self) -> None:
        history = self.repository.load_history_from_file(HF_DIRECT_FILE)

        self.assertEqual("2021 March 7, 11:16", format_commit_datetime(history.entries[0].commit_date, history.entries[0].commit_date_raw))

    def test_change_type_chips_use_per_type_classes(self) -> None:
        self.assertEqual("type-body", change_type_chip_class("Body"))
        self.assertEqual("type-introduction", change_type_chip_class("Introduction"))
        self.assertEqual("type-annotation", change_type_chip_class("Yannotationchnage"))

        chip_html = render_change_chip("Body")
        self.assertIn('class="chip type-body"', chip_html)
        self.assertIn(">Body<", chip_html)

    def test_truncate_display_text_keeps_prefix_and_ellipsis(self) -> None:
        value = "testRejectionWithFallbackRequestContextWithSemaphoreIsolatedAsynchronousObservable"

        self.assertEqual(
            "testRejectionWithFallbackRequestC...",
            truncate_display_text(value),
        )

    def test_render_diff_html_uses_split_rows_with_colors(self) -> None:
        diff_text = "@@ -1,2 +1,2 @@\n-return 1;\n+return 2;\n // sharedLine\n"

        rows = parse_unified_diff(diff_text)
        html_output = render_diff_html(diff_text, modal_id="diff-modal-test", title="Example.java")

        self.assertTrue(any(row["kind"] == "change" for row in rows))
        self.assertIn("diff-cell-del", html_output)
        self.assertIn("diff-cell-add", html_output)
        self.assertIn("Open split view", html_output)
        self.assertIn('id="diff-modal-test"', html_output)
        self.assertIn("Split Diff View", html_output)
        self.assertIn("Example.java", html_output)
        self.assertIn("github-split", html_output)
        self.assertIn("Source versions", html_output)
        self.assertIn('class="syntax-keyword"', html_output)
        self.assertIn('class="syntax-number"', html_output)
        self.assertIn('data-scroll-direction="left"', html_output)
        self.assertIn('data-scroll-direction="right"', html_output)
        self.assertNotIn("diff-unified-prefix", html_output)
        self.assertNotIn(">±<", html_output)

    def test_parse_commit_datetime_supports_year_month_day_24_hour_input(self) -> None:
        parsed = parse_commit_datetime("20/12/16 23:30 PM")

        self.assertIsNotNone(parsed)
        self.assertEqual("2016 December 20, 23:30", format_commit_datetime(parsed, ""))

    def test_parse_commit_datetime_prefers_day_month_year_when_first_number_cannot_be_month(self) -> None:
        parsed = parse_commit_datetime("25/02/14 22:56 PM")

        self.assertIsNotNone(parsed)
        self.assertEqual("2014 February 25, 22:56", format_commit_datetime(parsed, ""))

    def test_parse_commit_datetime_supports_midnight_with_am_marker(self) -> None:
        parsed = parse_commit_datetime("07/07/16 00:07 AM")

        self.assertIsNotNone(parsed)
        self.assertEqual("2016 July 7, 00:07", format_commit_datetime(parsed, ""))

    def test_parse_commit_datetime_prefers_day_month_year_for_ambiguous_numeric_dates(self) -> None:
        parsed = parse_commit_datetime("11/02/10 10:10 AM")

        self.assertIsNotNone(parsed)
        self.assertEqual("2010 February 11, 10:10", format_commit_datetime(parsed, ""))

    def test_load_historyfinder_from_direct_json_file(self) -> None:
        history = self.repository.load_history_from_file(HF_DIRECT_FILE)

        self.assertEqual("historyFinder", history.tool)
        self.assertEqual("toPrettyString", history.function_name)
        self.assertEqual(940, history.function_start_line)
        self.assertTrue(history.entries)
        self.assertTrue(history.entries[0].diff_url.startswith("https://github.com/google/auto/compare/"))

    def test_load_historyfinder_from_url_resolves_tar_member(self) -> None:
        history = self.repository.load_history_from_url(
            "https://github.com/cucumber/cucumber-jvm/blob/4d9dd9304fe05e15c445c6f3b4d0e364d7c70223/"
            "cucumber-core/src/test/java/io/cucumber/core/plugin/UTF8PrintWriterTest.java#L17",
            tool="historyFinder",
        )

        self.assertEqual("println", history.function_name)
        self.assertEqual("cucumber-jvm", history.project)
        self.assertGreaterEqual(len(history.entries), 1)

    def test_load_codeshovel_from_url_resolves_tar_member(self) -> None:
        history = self.repository.load_history_from_url(
            "https://github.com/apache/ant/blob/3ffea30ee459d9fc4b9a005d418a192157e0e3ac/"
            "src/tutorial/tasks-start-writing/src/HelloWorldTest.java#L49",
            tool="codeShovel",
        )

        self.assertEqual("testMessage", history.function_name)
        self.assertEqual("ant", history.project)
        self.assertEqual("Ybodychange", history.entries[0].change_types[0])

    def test_write_revision_links_and_update_note(self) -> None:
        temp_csv = REPOSITORY_ROOT / ".cache" / "test" / "history-viewer" / "cucumber-jvm-copy.csv"
        temp_csv.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SAMPLE_CSV, temp_csv)

        row_count = self.repository.write_revision_links(temp_csv, base_url="http://127.0.0.1:8765")
        self.assertGreater(row_count, 0)

        with temp_csv.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            first_row = next(reader)
            self.assertIn("revision_url", reader.fieldnames)
            self.assertIn("sample_csv=", first_row["revision_url"])
            self.assertIn("from_url=", first_row["revision_url"])
            self.assertIn("%23L17", first_row["revision_url"])

        updated = self.repository.update_sample_note(
            temp_csv,
            from_url=first_row["from_url"],
            to_url=first_row["to_url"],
            note="Strong same-commit coupling",
        )
        self.assertEqual("Strong same-commit coupling", updated.note)

        with temp_csv.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual("Strong same-commit coupling", rows[0]["note"])

    def test_find_related_production_methods_uses_t2p_change_before_fallbacks(self) -> None:
        with SAMPLE_CSV.open("r", encoding="utf-8", newline="") as handle:
            first_row = next(csv.DictReader(handle))

        related_methods, searched_labels = self.repository.find_related_production_methods(
            project=first_row["project"],
            from_url=first_row["from_url"],
            tool="historyFinder",
            sample_csv=str(SAMPLE_CSV),
        )

        self.assertTrue(related_methods)
        self.assertEqual("t2p-change/historyFinder/omc--nc--ncc", related_methods[0].source_label)
        self.assertEqual("t2p-change/historyFinder/omc--nc--ncc", searched_labels[0])

    def test_related_source_options_include_requested_directory_order(self) -> None:
        options = self.repository.related_source_options(tool="historyFinder", sample_csv=str(SAMPLE_CSV))

        self.assertEqual(
            [
                "t2p-change/historyFinder/omc--nc--ncc",
                "t2p-candidate",
                "m2m-tech",
                "fan-out",
            ],
            options,
        )

    def test_find_calling_test_methods_uses_t2p_change_before_fallbacks(self) -> None:
        with SAMPLE_CSV.open("r", encoding="utf-8", newline="") as handle:
            first_row = next(csv.DictReader(handle))

        calling_methods, searched_labels = self.repository.find_calling_test_methods(
            project=first_row["project"],
            to_url=first_row["to_url"],
            tool="historyFinder",
            sample_csv=str(SAMPLE_CSV),
        )

        self.assertTrue(calling_methods)
        self.assertEqual("t2p-change/historyFinder/omc--nc--ncc", calling_methods[0].source_label)
        self.assertEqual("t2p-change/historyFinder/omc--nc--ncc", searched_labels[0])
        self.assertEqual(first_row["from_url"], calling_methods[0].from_url)

    def test_revision_route_renders_comparison_page(self) -> None:
        app = create_app(cache_directory=str(CACHE_DIRECTORY), data_directory=str(DATA_DIRECTORY))
        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/revision",
            "QUERY_STRING": (
                "tool=historyFinder&sample_csv="
                f"{SAMPLE_CSV}"
                "&from_url=https%3A%2F%2Fgithub.com%2Fcucumber%2Fcucumber-jvm%2Fblob%2F4d9dd9304fe05e15c445c6f3b4d0e364d7c70223%2F"
                "cucumber-core%2Fsrc%2Ftest%2Fjava%2Fio%2Fcucumber%2Fcore%2Fplugin%2FUTF8PrintWriterTest.java%23L17"
                "&to_url=https%3A%2F%2Fgithub.com%2Fcucumber%2Fcucumber-jvm%2Fblob%2F4d9dd9304fe05e15c445c6f3b4d0e364d7c70223%2F"
                "cucumber-core%2Fsrc%2Fmain%2Fjava%2Fio%2Fcucumber%2Fcore%2Fplugin%2FUTF8PrintWriter.java%23L29"
            ),
            "wsgi.input": BytesIO(b""),
            "CONTENT_LENGTH": "0",
            "SERVER_NAME": "127.0.0.1",
            "SERVER_PORT": "8765",
            "wsgi.url_scheme": "http",
        }

        status_holder: list[str] = []

        def start_response(status: str, _headers: list[tuple[str, str]]) -> None:
            status_holder.append(status)

        body = b"".join(app(environ, start_response)).decode("utf-8")

        self.assertEqual("200 OK", status_holder[0])
        self.assertIn("Revision Viewer", body)
        self.assertIn("Save manual review notes back to the sampled CSV", body)
        self.assertIn("UTF8PrintWriterTest.java:17", body)
        self.assertIn("Tested Production Methods", body)
        self.assertIn("Calling Test Methods", body)
        self.assertIn("t2p-change/historyFinder/omc--nc--ncc", body)
        self.assertIn('name="related_source"', body)
        self.assertIn('name="calling_source"', body)
        self.assertIn("Open This Revision With Tool", body)
        self.assertIn("codeShovel", body)
        self.assertIn("historyFinder (current)", body)
        self.assertNotIn("<th>Method</th>", body)
        self.assertNotIn("<th>Link</th>", body)
        self.assertNotIn("<th>File</th>", body)
        self.assertNotIn("Actual Source", body)

    def test_sample_directory_route_lists_csv_files(self) -> None:
        app = create_app(cache_directory=str(CACHE_DIRECTORY), data_directory=str(DATA_DIRECTORY))
        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/sample",
            "QUERY_STRING": f"sample_dir={SAMPLE_DIR}",
            "wsgi.input": BytesIO(b""),
            "CONTENT_LENGTH": "0",
            "SERVER_NAME": "127.0.0.1",
            "SERVER_PORT": "8765",
            "wsgi.url_scheme": "http",
        }

        status_holder: list[str] = []

        def start_response(status: str, _headers: list[tuple[str, str]]) -> None:
            status_holder.append(status)

        body = b"".join(app(environ, start_response)).decode("utf-8")

        self.assertEqual("200 OK", status_holder[0])
        self.assertIn("Sample Directory", body)
        self.assertIn("cucumber-jvm.csv", body)
        self.assertIn("CSV Files", body)

    def test_history_json_api_returns_raw_history(self) -> None:
        app = create_app(cache_directory=str(CACHE_DIRECTORY), data_directory=str(DATA_DIRECTORY))
        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/api/history-json",
            "QUERY_STRING": (
                "tool=historyFinder"
                "&from_url=https%3A%2F%2Fgithub.com%2Fcucumber%2Fcucumber-jvm%2Fblob%2F4d9dd9304fe05e15c445c6f3b4d0e364d7c70223%2F"
                "cucumber-core%2Fsrc%2Ftest%2Fjava%2Fio%2Fcucumber%2Fcore%2Fplugin%2FUTF8PrintWriterTest.java%23L17"
                "&side=from"
            ),
            "wsgi.input": BytesIO(b""),
            "CONTENT_LENGTH": "0",
            "SERVER_NAME": "127.0.0.1",
            "SERVER_PORT": "8765",
            "wsgi.url_scheme": "http",
        }

        captured: dict[str, object] = {}

        def start_response(status: str, headers: list[tuple[str, str]]) -> None:
            captured["status"] = status
            captured["headers"] = headers

        body = b"".join(app(environ, start_response)).decode("utf-8")

        self.assertEqual("200 OK", captured["status"])
        self.assertIn('"functionName": "println"', body)
        self.assertTrue(any(header == ("Content-Type", "application/json; charset=utf-8") for header in captured["headers"]))

    def test_history_json_api_can_force_download(self) -> None:
        app = create_app(cache_directory=str(CACHE_DIRECTORY), data_directory=str(DATA_DIRECTORY))
        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/api/history-json",
            "QUERY_STRING": (
                "tool=historyFinder"
                "&to_url=https%3A%2F%2Fgithub.com%2Fcucumber%2Fcucumber-jvm%2Fblob%2F4d9dd9304fe05e15c445c6f3b4d0e364d7c70223%2F"
                "cucumber-core%2Fsrc%2Fmain%2Fjava%2Fio%2Fcucumber%2Fcore%2Fplugin%2FUTF8PrintWriter.java%23L29"
                "&side=to&download=1"
            ),
            "wsgi.input": BytesIO(b""),
            "CONTENT_LENGTH": "0",
            "SERVER_NAME": "127.0.0.1",
            "SERVER_PORT": "8765",
            "wsgi.url_scheme": "http",
        }

        captured: dict[str, object] = {}

        def start_response(status: str, headers: list[tuple[str, str]]) -> None:
            captured["status"] = status
            captured["headers"] = headers

        _body = b"".join(app(environ, start_response)).decode("utf-8")

        self.assertEqual("200 OK", captured["status"])
        self.assertTrue(any(header[0] == "Content-Disposition" and header[1].endswith(".json\"") for header in captured["headers"]))


if __name__ == "__main__":
    unittest.main()

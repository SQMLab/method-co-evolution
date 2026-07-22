import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

SRC_DIRECTORY = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SRC_DIRECTORY))

import mhc.main as mhc_main
import mhc.method_metadata_scanner as metadata_scanner
import mhc.util as util


class _FakeMetadata:
    def __init__(
        self,
        name: str,
        url: str,
        annotations: str,
        annotations_fqn: str,
        frameworks: str,
        javadoc: str,
    ):
        self._name = name
        self._url = url
        self._annotations = annotations
        self._annotations_fqn = annotations_fqn
        self._frameworks = frameworks
        self._javadoc = javadoc

    def getName(self):
        return self._name

    def getUrl(self):
        return self._url

    def getAnnotations(self):
        return self._annotations

    def getAnnotationsFqn(self):
        return self._annotations_fqn

    def getFrameworks(self):
        return self._frameworks

    def getJavadoc(self):
        return self._javadoc


class _FakeScanner:
    init_calls = []
    fail = False

    @classmethod
    def getInstance(cls):
        return cls()

    def init(self, *args):
        self.init_calls.append(args)

    def scanMethodMetadata(self, file):
        if self.fail:
            raise RuntimeError(f"Unable to parse {file}")
        return [
            _FakeMetadata(
                "run",
                "https://github.com/example/demo/blob/abc123/src/Demo.java#L8",
                '["Deprecated","Tag(\\"fast\\")"]',
                '["java.lang.Deprecated","demo.Tag"]',
                "#junit #quicktheories",
                "/** Runs. */",
            ),
            _FakeMetadata(
                "Demo",
                "https://github.com/example/demo/blob/abc123/src/Demo.java#L12",
                "[]",
                "[]",
                "#junit",
                "",
            ),
        ]


class MethodMetadataGenerationTestCase(unittest.TestCase):
    def setUp(self):
        _FakeScanner.init_calls = []
        _FakeScanner.fail = False

    def _repository_df(self):
        return pd.DataFrame(
            [
                {
                    "project": "demo",
                    "url": "https://github.com/example/demo",
                    "updated_hash": "abc123",
                }
            ]
        )

    def _write_method_input(self, root: Path, test_case: bool = True):
        method_dir = root / "method"
        method_dir.mkdir(parents=True, exist_ok=True)
        artifact = "#test-code #test-case-method" if test_case else "#main-code"
        pd.DataFrame(
            [
                {
                    "url": "https://github.com/example/demo/blob/abc123/src/Demo.java#L8",
                    "artifact": artifact,
                },
                {
                    "url": "https://github.com/example/demo/blob/abc123/src/Demo.java#L12",
                    "artifact": "#main-code",
                },
            ]
        ).to_csv(method_dir / "demo.csv", index=False)

    def test_generates_expected_csv_schema_and_values(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            repository_directory = root / "repository"
            source_file = repository_directory / "demo" / "src" / "Demo.java"
            source_file.parent.mkdir(parents=True)
            source_file.write_text("class Demo {}\n", encoding="utf-8")
            self._write_method_input(root)

            with patch.object(
                metadata_scanner,
                "clone_and_checkout_commit",
            ), patch("jpype.JClass", return_value=_FakeScanner):
                output_files = metadata_scanner.scan_method_metadata(
                    self._repository_df(),
                    str(repository_directory),
                    str(root),
                    str(root),
                )

            self.assertEqual(
                [str(root / "method-metadata" / "demo.csv")],
                output_files,
            )
            output_df = pd.read_csv(output_files[0], keep_default_na=False, na_filter=False)
            self.assertEqual(
                metadata_scanner.METHOD_METADATA_COLUMNS,
                output_df.columns.tolist(),
            )
            self.assertNotIn("artifact", output_df.columns)
            self.assertEqual(["Deprecated", 'Tag("fast")'], json.loads(output_df.loc[0, "annotations"]))
            self.assertEqual(
                ["java.lang.Deprecated", "demo.Tag"],
                json.loads(output_df.loc[0, "annotations_fqn"]),
            )
            self.assertEqual("/** Runs. */", output_df.loc[0, "javadoc"])
            self.assertEqual("#junit #quicktheories", output_df.loc[0, "frameworks"])
            self.assertEqual("", output_df.loc[1, "frameworks"])
            self.assertEqual([], json.loads(output_df.loc[1, "annotations"]))
            self.assertEqual(
                (
                    "demo",
                    str(repository_directory / "demo"),
                    "https://github.com/example/demo",
                    "abc123",
                    False,
                ),
                _FakeScanner.init_calls[0],
            )

    def test_parse_failure_is_written_as_retryable_error(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            repository_directory = root / "repository"
            source_file = repository_directory / "demo" / "src" / "Broken.java"
            source_file.parent.mkdir(parents=True)
            source_file.write_text("class Broken {\n", encoding="utf-8")
            self._write_method_input(root)
            _FakeScanner.fail = True

            with patch.object(
                metadata_scanner,
                "clone_and_checkout_commit",
            ), patch("jpype.JClass", return_value=_FakeScanner):
                metadata_scanner.scan_method_metadata(
                    self._repository_df(),
                    str(repository_directory),
                    str(root),
                    str(root),
                )

            output_df = pd.read_csv(root / "method-metadata" / "demo.csv")
            error_df = pd.read_csv(
                root / ".method-metadata-error" / "demo.csv",
                keep_default_na=False,
                na_filter=False,
            )
            self.assertTrue(output_df.empty)
            self.assertEqual(1, len(error_df))
            self.assertTrue((root / ".method-metadata" / "demo.csv").exists())
            self.assertEqual(
                metadata_scanner.METHOD_METADATA_ERROR_MARKER,
                error_df.loc[0, metadata_scanner.METHOD_METADATA_FLAG_COLUMN],
            )
            self.assertIn("Unable to parse", error_df.loc[0, metadata_scanner.METHOD_METADATA_ERROR_COLUMN])

    def test_requires_method_input(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            repository_directory = root / "repository"
            (repository_directory / "demo").mkdir(parents=True)

            with patch.object(metadata_scanner, "clone_and_checkout_commit"), patch(
                "jpype.JClass", return_value=_FakeScanner
            ):
                with self.assertRaisesRegex(FileNotFoundError, "requires method input"):
                    metadata_scanner.scan_method_metadata(
                        self._repository_df(),
                        str(repository_directory),
                        str(root),
                        str(root),
                    )

    def test_suppresses_frameworks_for_non_test_case_method(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            repository_directory = root / "repository"
            source_file = repository_directory / "demo" / "src" / "Demo.java"
            source_file.parent.mkdir(parents=True)
            source_file.write_text("class Demo {}\n", encoding="utf-8")
            self._write_method_input(root, test_case=False)

            with patch.object(
                metadata_scanner,
                "clone_and_checkout_commit",
            ), patch("jpype.JClass", return_value=_FakeScanner):
                output_files = metadata_scanner.scan_method_metadata(
                    self._repository_df(),
                    str(repository_directory),
                    str(root),
                    str(root),
                )

            output_df = pd.read_csv(output_files[0], keep_default_na=False, na_filter=False)
            self.assertEqual(["", ""], output_df["frameworks"].tolist())

    def test_legacy_cache_schema_is_not_current(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            cache_file = Path(temp_directory) / "legacy.csv"
            pd.DataFrame(
                [{"project": "demo", "url": "test", "annotations": "[]"}]
            ).to_csv(cache_file, index=False)
            self.assertFalse(metadata_scanner._metadata_cache_schema_current(str(cache_file)))

    def test_finalize_waits_for_all_files_and_writes_success_after_retry(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            cache_file = root / ".method-metadata" / "demo.csv"
            output_file = root / "method-metadata" / "demo.csv"
            error_file = root / ".method-metadata-error" / "demo.csv"
            cache_file.parent.mkdir(parents=True)
            rows = [
                metadata_scanner._build_metadata_error(
                    "demo",
                    "src/A.java",
                    "abc123",
                    "first failure",
                ),
                {
                    "project": "demo",
                    "name": "run",
                    "url": "https://github.com/example/demo/blob/abc123/src/A.java#L1",
                    "annotations": '["Test"]',
                    "annotations_fqn": '["org.junit.Test"]',
                    "frameworks": "#junit",
                    "javadoc": "",
                    metadata_scanner.METHOD_METADATA_FILE_COLUMN: "src/A.java",
                    metadata_scanner.METHOD_METADATA_HASH_COLUMN: "abc123",
                    metadata_scanner.METHOD_METADATA_FLAG_COLUMN: None,
                    metadata_scanner.METHOD_METADATA_ERROR_COLUMN: None,
                },
                metadata_scanner._build_metadata_marker(
                    "demo",
                    "src/A.java",
                    "abc123",
                ),
            ]
            pd.DataFrame(
                rows,
                columns=metadata_scanner.METHOD_METADATA_CACHE_COLUMNS,
            ).to_csv(cache_file, index=False)

            self.assertFalse(
                metadata_scanner._finalize_metadata_outputs(
                    str(cache_file),
                    str(output_file),
                    str(error_file),
                    {"src/A.java", "src/B.java"},
                    {"https://github.com/example/demo/blob/abc123/src/A.java#L1"},
                    delete_tmp=False,
                )
            )
            self.assertTrue(
                metadata_scanner._finalize_metadata_outputs(
                    str(cache_file),
                    str(output_file),
                    str(error_file),
                    {"src/A.java"},
                    {"https://github.com/example/demo/blob/abc123/src/A.java#L1"},
                    delete_tmp=False,
                )
            )
            output_df = pd.read_csv(output_file)
            self.assertEqual(["run"], output_df["name"].tolist())
            self.assertFalse(error_file.exists())

    def test_error_rows_are_retried_by_default(self):
        cache_df = pd.DataFrame(
            [
                metadata_scanner._build_metadata_error(
                    "demo",
                    "src/Broken.java",
                    "abc123",
                    "parse failure",
                )
            ],
            columns=metadata_scanner.METHOD_METADATA_CACHE_COLUMNS,
        )

        self.assertEqual(
            set(),
            metadata_scanner._completed_metadata_files(cache_df),
        )
        self.assertEqual(
            {"src/Broken.java"},
            metadata_scanner._completed_metadata_files(
                cache_df,
                retry_errors=False,
            ),
        )

    def test_shards_are_combined_by_merge_only(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            repository_directory = root / "repository"
            project_directory = repository_directory / "demo" / "src"
            project_directory.mkdir(parents=True)
            self._write_method_input(root)

            files_by_shard = {1: [], 2: []}
            candidate = 0
            while not all(files_by_shard.values()):
                relative_file = f"src/Type{candidate}.java"
                assigned_shard = util.stable_shard_for_key(relative_file, 2)
                files_by_shard[assigned_shard].append(relative_file)
                (repository_directory / "demo" / relative_file).write_text(
                    f"class Type{candidate} {{}}\n",
                    encoding="utf-8",
                )
                candidate += 1

            with patch.object(
                metadata_scanner,
                "clone_and_checkout_commit",
            ), patch("jpype.JClass", return_value=_FakeScanner):
                for shard in (1, 2):
                    metadata_scanner.scan_method_metadata(
                        self._repository_df(),
                        str(repository_directory),
                        str(root),
                        str(root),
                        shards=2,
                        shard=shard,
                        max_workers=2,
                    )

                output_file = root / "method-metadata" / "demo.csv"
                self.assertFalse(output_file.exists())

                metadata_scanner.scan_method_metadata(
                    self._repository_df(),
                    str(repository_directory),
                    str(root),
                    str(root),
                    shards=2,
                    merge_only=True,
                )

            output_df = pd.read_csv(output_file)
            self.assertEqual(candidate * 2, len(output_df))

    @patch("mhc.main._build_method_history_collector")
    def test_cli_dispatches_method_metadata_options(self, mock_build_collector):
        mock_collector = mock_build_collector.return_value
        mock_collector.repository_df = pd.DataFrame([{"project": "demo"}])

        mhc_main.main(
            [
                "method-metadata",
                "--workspace-directory",
                "workspace",
                "--project",
                "demo",
                "--java-options",
                "-Xmx2g",
                "--replace",
                "--shards",
                "3",
                "--shard",
                "2",
                "--retry-errors",
                "false",
                "--merge-threshold",
                "25",
                "--merge-interval-seconds",
                "10",
                "--max-workers",
                "4",
                "--init-reset-interval-files",
                "50",
            ]
        )

        mock_collector.generate_method_metadata.assert_called_once_with(
            ["demo"],
            "-Xmx2g",
            True,
            3,
            2,
            False,
            False,
            False,
            False,
            False,
            25,
            10,
            4,
            50,
        )

    def test_method_code_schema_remains_unchanged(self):
        from mhc.method_scanner import METHOD_CODE_COLUMNS

        self.assertEqual(
            [
                "project",
                "name",
                "url",
                "artifact",
                "start_line",
                "end_line",
                "code",
            ],
            METHOD_CODE_COLUMNS,
        )


if __name__ == "__main__":
    unittest.main()

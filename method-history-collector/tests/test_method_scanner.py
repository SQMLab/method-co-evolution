import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

SRC_DIRECTORY = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SRC_DIRECTORY))

import mhc.method_scanner as ms
import mhc.util as util


class FakeJavaMethod:
    def __init__(self, repository_url: str, commit_hash: str, file_path: str):
        method_name = Path(file_path).stem
        self.name = f"{method_name}_method"
        self.url = util.format_to_git_url(repository_url, commit_hash, file_path, 1)
        self.artifact = "production"
        self.start_line = 1
        self.end_line = 2
        self.expression = "method"
        self.file = file_path
        self.pkg = "demo.pkg"
        self.fqn = f"demo.pkg.{method_name}"
        self.fqs = [self.fqn]
        self.fqs_alt = [self.fqn]
        self.hash = commit_hash

    def getName(self):
        return self.name

    def getUrl(self):
        return self.url

    def getArtifact(self):
        return self.artifact

    def getStartLine(self):
        return self.start_line

    def getEndLine(self):
        return self.end_line

    def getExpression(self):
        return self.expression

    def getFile(self):
        return self.file

    def getPkg(self):
        return self.pkg

    def getFqn(self):
        return self.fqn

    def getFqs(self):
        return self.fqs

    def getFqsAlt(self):
        return self.fqs_alt

    def getHash(self):
        return self.hash


class FakeMethodScannerImpl:
    scanned_files = []

    def scanMethod(self, _repository_directory, repository_url, commit_hash, file_without_base):
        FakeMethodScannerImpl.scanned_files.append(file_without_base)
        return [FakeJavaMethod(repository_url, commit_hash, file_without_base)]


class MethodScannerCacheTestCase(unittest.TestCase):
    def _repository_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "project": "demo-project",
                    "url": "https://github.com/example/demo-project",
                    "updated_hash": "abc123",
                }
            ]
        )

    def _create_java_file(self, file_path: Path) -> None:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("class Demo { void run() {} }", encoding="utf-8")

    def test_scan_method_uses_method_cache_file_on_resume(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            repository_directory = root / "repositories"
            data_directory = root / "data"
            cache_directory = root / "cache"
            project_directory = repository_directory / "demo-project"

            self._create_java_file(project_directory / "src" / "Alpha.java")
            self._create_java_file(project_directory / "src" / "Beta.java")

            repository_df = self._repository_df()
            output_method_file = Path(util.format_method_list_file(str(data_directory), "demo-project"))
            method_cache_file = Path(
                util.format_method_cache_file(str(data_directory), "demo-project", "abc123")
            )

            seed_rows = pd.DataFrame(
                [
                    {
                        "project": "demo-project",
                        "name": "Alpha_method",
                        "url": "https://github.com/example/demo-project/blob/abc123/src/Alpha.java#L1",
                        "artifact": "production",
                        "start_line": 1,
                        "end_line": 2,
                        "expression": "method",
                        "file": "src/Alpha.java",
                        "pkg": "demo.pkg",
                        "fqn": "demo.pkg.Alpha",
                        "fqs": "['demo.pkg.Alpha']",
                        "fqs_alt": "['demo.pkg.Alpha']",
                        "hash": "abc123",
                        "parser": "javaparser",
                    },
                    ms._build_scan_marker_row("demo-project", "src/Alpha.java", "abc123"),
                ]
            )
            method_cache_file.parent.mkdir(parents=True, exist_ok=True)
            seed_rows.to_csv(method_cache_file, index=False)

            FakeMethodScannerImpl.scanned_files = []
            with patch("jpype.JClass", return_value=FakeMethodScannerImpl), patch.object(
                ms, "clone_and_checkout_commit"
            ):
                ms.scan_method(
                    repository_df,
                    str(repository_directory),
                    str(data_directory),
                    str(cache_directory),
                )

            self.assertEqual(FakeMethodScannerImpl.scanned_files, ["src/Beta.java"])
            self.assertFalse(method_cache_file.exists())
            self.assertTrue(output_method_file.exists())
            resumed_df = pd.read_csv(output_method_file)
            self.assertEqual(sorted(resumed_df["file"].tolist()), ["src/Alpha.java", "src/Beta.java"])
            self.assertNotIn(ms.SCAN_MARKER_PARSER, resumed_df["parser"].tolist())

    def test_scan_method_appends_cache_before_completion(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            repository_directory = root / "repositories"
            data_directory = root / "data"
            cache_directory = root / "cache"
            project_directory = repository_directory / "demo-project"

            self._create_java_file(project_directory / "src" / "Alpha.java")
            self._create_java_file(project_directory / "src" / "Beta.java")

            repository_df = self._repository_df()
            output_method_file = Path(util.format_method_list_file(str(data_directory), "demo-project"))
            FakeMethodScannerImpl.scanned_files = []

            with patch("jpype.JClass", return_value=FakeMethodScannerImpl), patch.object(
                ms, "clone_and_checkout_commit"
            ), patch.object(
                ms, "SCAN_METHOD_FLUSH_INTERVAL_SECONDS", 0
            ), patch.object(
                ms, "_flush_method_scan_buffers", wraps=ms._flush_method_scan_buffers
            ) as flush_results:
                ms.scan_method(
                    repository_df,
                    str(repository_directory),
                    str(data_directory),
                    str(cache_directory),
                )

            self.assertGreaterEqual(flush_results.call_count, 3)
            self.assertTrue(output_method_file.exists())


if __name__ == "__main__":
    unittest.main()

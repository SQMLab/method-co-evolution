import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SRC_DIRECTORY = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SRC_DIRECTORY))

import mhc.main as mhc_main


class TestCliArgs(unittest.TestCase):
    @patch("mhc.main._build_method_history_collector")
    def test_scan_method_accepts_dash_prefixed_java_options(self, mock_build_collector):
        mock_mhc_instance = mock_build_collector.return_value

        mhc_main.main(
            [
                "scan-method",
                "--cache-directory",
                ".cache",
                "--repository-directory",
                ".cache/repository",
                "--data-directory",
                ".cache/data",
                "--jar-directory",
                ".cache/jar",
                "--java-options",
                "-Xmx2g",
                "--project",
                "checkstyle",
            ]
        )

        mock_mhc_instance.scan_method.assert_called_once_with(
            ["checkstyle"],
            "-Xmx2g",
        )


if __name__ == "__main__":
    unittest.main()

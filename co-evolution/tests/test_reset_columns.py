import csv
import sys
import tempfile
import unittest
from pathlib import Path


SRC_DIRECTORY = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SRC_DIRECTORY))

from ptc.sample.reset_columns import main, parse_columns, reset_columns


class ResetColumnsTest(unittest.TestCase):
    def test_default_columns_are_cleared_and_other_values_are_preserved(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            input_dir = root / "input"
            output_dir = root / "output"
            input_dir.mkdir()
            self.write_csv(
                input_dir / "project.csv",
                ["project", "label", "tags", "notes", "from_url"],
                [
                    {"project": "demo", "label": "1", "tags": "reviewed", "notes": "keep?", "from_url": "test://A"},
                    {"project": "demo", "label": "0", "tags": "#old", "notes": "manual", "from_url": "test://B"},
                ],
            )

            results = reset_columns(input_dir, output_dir, ["label", "tags", "notes"])

            self.assertEqual(1, len(results))
            self.assertEqual(6, results[0].reset_cells)
            fieldnames, rows = self.read_csv(output_dir / "project.csv")
            self.assertEqual(["project", "label", "tags", "notes", "from_url"], fieldnames)
            self.assertEqual(["", ""], [row["label"] for row in rows])
            self.assertEqual(["", ""], [row["tags"] for row in rows])
            self.assertEqual(["", ""], [row["notes"] for row in rows])
            self.assertEqual(["test://A", "test://B"], [row["from_url"] for row in rows])

    def test_custom_columns_are_supported(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            input_dir = root / "input"
            output_dir = root / "output"
            input_dir.mkdir()
            self.write_csv(
                input_dir / "project.csv",
                ["label", "reviewer", "notes"],
                [{"label": "1", "reviewer": "Ada", "notes": "done"}],
            )

            reset_columns(input_dir, output_dir, parse_columns("reviewer, notes"))

            _, rows = self.read_csv(output_dir / "project.csv")
            self.assertEqual("1", rows[0]["label"])
            self.assertEqual("", rows[0]["reviewer"])
            self.assertEqual("", rows[0]["notes"])

    def test_nested_csv_files_are_ignored(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            input_dir = root / "input"
            output_dir = root / "output"
            nested_dir = input_dir / "nested"
            nested_dir.mkdir(parents=True)
            self.write_csv(input_dir / "top.csv", ["label", "tags", "notes"], [{"label": "1", "tags": "a", "notes": "b"}])
            self.write_csv(nested_dir / "nested.csv", ["label", "tags", "notes"], [{"label": "1", "tags": "a", "notes": "b"}])

            reset_columns(input_dir, output_dir, ["label", "tags", "notes"])

            self.assertTrue((output_dir / "top.csv").exists())
            self.assertFalse((output_dir / "nested.csv").exists())
            self.assertFalse((output_dir / "nested").exists())

    def test_missing_columns_abort_before_any_files_are_written(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            input_dir = root / "input"
            output_dir = root / "output"
            input_dir.mkdir()
            self.write_csv(input_dir / "good.csv", ["label", "tags", "notes"], [{"label": "1", "tags": "a", "notes": "b"}])
            self.write_csv(input_dir / "bad.csv", ["label", "notes"], [{"label": "0", "notes": "c"}])

            with self.assertRaises(ValueError):
                reset_columns(input_dir, output_dir, ["label", "tags", "notes"])

            self.assertFalse(output_dir.exists())

    def test_same_input_and_output_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            input_dir = Path(temp_directory)
            self.write_csv(input_dir / "project.csv", ["label", "tags", "notes"], [{"label": "1", "tags": "a", "notes": "b"}])

            with self.assertRaises(ValueError):
                reset_columns(input_dir, input_dir, ["label", "tags", "notes"])

    def test_existing_output_files_are_overwritten_and_unrelated_files_remain(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            input_dir = root / "input"
            output_dir = root / "output"
            input_dir.mkdir()
            output_dir.mkdir()
            self.write_csv(input_dir / "project.csv", ["label", "tags", "notes"], [{"label": "1", "tags": "a", "notes": "b"}])
            self.write_csv(output_dir / "project.csv", ["old"], [{"old": "value"}])
            unrelated_file = output_dir / "README.txt"
            unrelated_file.write_text("untouched", encoding="utf-8")

            reset_columns(input_dir, output_dir, ["label", "tags", "notes"])

            fieldnames, rows = self.read_csv(output_dir / "project.csv")
            self.assertEqual(["label", "tags", "notes"], fieldnames)
            self.assertEqual({"label": "", "tags": "", "notes": ""}, rows[0])
            self.assertEqual("untouched", unrelated_file.read_text(encoding="utf-8"))

    def test_main_uses_default_columns(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            input_dir = root / "input"
            output_dir = root / "output"
            input_dir.mkdir()
            self.write_csv(input_dir / "project.csv", ["label", "tags", "notes"], [{"label": "1", "tags": "a", "notes": "b"}])

            exit_code = main(["--input-dir", str(input_dir), "--output-dir", str(output_dir)])

            self.assertEqual(0, exit_code)
            _, rows = self.read_csv(output_dir / "project.csv")
            self.assertEqual({"label": "", "tags": "", "notes": ""}, rows[0])

    def test_parse_columns_rejects_empty_and_duplicate_values(self):
        with self.assertRaises(Exception):
            parse_columns(" , ")
        with self.assertRaises(Exception):
            parse_columns("label,tags,label")

    @staticmethod
    def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    @staticmethod
    def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            return list(reader.fieldnames or []), [dict(row) for row in reader]


if __name__ == "__main__":
    unittest.main()

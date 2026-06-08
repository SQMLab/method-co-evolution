from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path


DEFAULT_COLUMNS = ["label", "tags", "notes"]


@dataclass(frozen=True)
class CsvResetPlan:
    input_file: Path
    output_file: Path
    fieldnames: list[str]
    rows: list[dict[str, str]]


@dataclass(frozen=True)
class CsvResetResult:
    input_file: Path
    output_file: Path
    rows: int
    reset_cells: int


def parse_columns(value: str) -> list[str]:
    columns = [part.strip() for part in value.split(",") if part.strip()]
    if not columns:
        raise argparse.ArgumentTypeError("--columns must include at least one column")
    duplicates = sorted({column for column in columns if columns.count(column) > 1})
    if duplicates:
        raise argparse.ArgumentTypeError(f"duplicate column(s): {', '.join(duplicates)}")
    return columns


def collect_csv_files(input_dir: Path) -> list[Path]:
    return sorted(path for path in input_dir.glob("*.csv") if path.is_file())


def build_reset_plans(input_dir: Path, output_dir: Path, columns: list[str]) -> list[CsvResetPlan]:
    csv_files = collect_csv_files(input_dir)
    if not csv_files:
        raise ValueError(f"no top-level CSV files found in input directory: {input_dir}")

    plans: list[CsvResetPlan] = []
    missing_by_file: list[tuple[Path, list[str]]] = []
    for csv_file in csv_files:
        with csv_file.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            missing = [column for column in columns if column not in fieldnames]
            if missing:
                missing_by_file.append((csv_file, missing))
                continue
            rows = [dict(row) for row in reader]
        plans.append(
            CsvResetPlan(
                input_file=csv_file,
                output_file=output_dir / csv_file.name,
                fieldnames=list(fieldnames),
                rows=rows,
            )
        )

    if missing_by_file:
        details = "; ".join(
            f"{csv_file}: missing {', '.join(missing)}" for csv_file, missing in missing_by_file
        )
        raise ValueError(details)
    return plans


def reset_columns(input_dir: Path, output_dir: Path, columns: list[str]) -> list[CsvResetResult]:
    input_dir = input_dir.expanduser()
    output_dir = output_dir.expanduser()
    if not input_dir.is_dir():
        raise ValueError(f"--input-dir does not exist or is not a directory: {input_dir}")
    if input_dir.resolve() == output_dir.resolve():
        raise ValueError("--input-dir and --output-dir must be different directories")
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError(f"--output-dir exists and is not a directory: {output_dir}")

    plans = build_reset_plans(input_dir, output_dir, columns)
    output_dir.mkdir(parents=True, exist_ok=True)

    results: list[CsvResetResult] = []
    for plan in plans:
        rows = []
        for row in plan.rows:
            reset_row = dict(row)
            for column in columns:
                reset_row[column] = ""
            rows.append(reset_row)

        with plan.output_file.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=plan.fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        result = CsvResetResult(
            input_file=plan.input_file,
            output_file=plan.output_file,
            rows=len(rows),
            reset_cells=len(rows) * len(columns),
        )
        results.append(result)
        print(f"{plan.input_file} -> {plan.output_file}: {result.rows} row(s), {result.reset_cells} cell(s) reset")

    print(f"Reset {sum(result.reset_cells for result in results)} cell(s) in {len(results)} file(s).")
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Copy top-level CSV files while clearing selected columns.",
    )
    parser.add_argument("--input-dir", type=Path, required=True, help="Directory containing input CSV files.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory where reset CSV files are written.")
    parser.add_argument(
        "--columns",
        type=parse_columns,
        default=DEFAULT_COLUMNS,
        help="Comma-separated columns to clear. Defaults to label,tags,notes.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        reset_columns(args.input_dir, args.output_dir, args.columns)
    except ValueError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

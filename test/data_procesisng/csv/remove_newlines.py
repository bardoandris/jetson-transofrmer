import argparse
import csv
from pathlib import Path


def remove_newlines(value: str) -> str:
    return value.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")


def find_csv_files(paths: list[Path]) -> list[Path]:
    csv_files: set[Path] = set()
    for path in paths:
        if path.is_dir():
            csv_files.update(
                file_path
                for file_path in path.rglob("*")
                if file_path.is_file()
                and file_path.suffix.lower() == ".csv"
                and not file_path.stem.endswith("_cleaned")
            )
        elif path.is_file() and path.suffix.lower() == ".csv":
            csv_files.add(path)
        else:
            raise FileNotFoundError(f"CSV file or directory not found: {path}")
    return sorted(csv_files)


def clean_csv(source: Path, in_place: bool = False) -> Path:
    with source.open("r", encoding="utf-8-sig", newline="") as input_file:
        rows = list(csv.reader(input_file))

    output = (
        source
        if in_place
        else source.with_name(f"{source.stem}_cleaned{source.suffix}")
    )
    with output.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.writer(output_file)
        writer.writerows(
            [remove_newlines(value) for value in row]
            for row in rows
        )
    return output


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Remove embedded line breaks from CSV cell values."
    )
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="CSV file(s) or directories to search recursively for CSV files.",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite each input CSV instead of writing *_cleaned.csv copies.",
    )
    args = parser.parse_args()

    csv_files = find_csv_files(args.paths)
    if not csv_files:
        parser.error("No CSV files found in the provided paths.")

    for source in csv_files:
        print(f"Cleaned {source} -> {clean_csv(source, args.in_place)}")


if __name__ == "__main__":
    main()

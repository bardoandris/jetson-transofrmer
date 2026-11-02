"""Split tuple-form image dimensions in test-result CSVs into width/height."""

import argparse
import ast
import csv
import os
import tempfile
from pathlib import Path


def dimensions(value: str) -> tuple[int | str, int | str]:
	"""Parse a value such as ``(500, 500)``; return blanks if invalid."""
	try:
		parsed = ast.literal_eval(value)
		if (
			isinstance(parsed, (tuple, list))
			and len(parsed) == 2
			and all(isinstance(item, (int, float)) for item in parsed)
		):
			return parsed[0], parsed[1]
	except (ValueError, SyntaxError, TypeError):
		pass
	return "", ""


def process_csv(path: Path) -> bool:
	with path.open("r", encoding="utf-8-sig", newline="") as source:
		reader = csv.DictReader(source)
		fieldnames = reader.fieldnames or []
		# Current inference CSVs call this field image_size; also accept
		# tuple-valued resolution columns in older result files.
		dimension_column = next(
			(name for name in ("image_size", "resolution") if name in fieldnames),
			None,
		)
		if dimension_column is None:
			return False
		rows = list(reader)

	output_fields = [
		name for name in fieldnames if name not in {dimension_column, "width", "height"}
	] + ["width", "height"]
	directory = path.parent
	fd, temporary_name = tempfile.mkstemp(
		dir=directory, prefix=f".{path.name}.", suffix=".tmp"
	)
	try:
		with os.fdopen(fd, "w", encoding="utf-8", newline="") as output:
			writer = csv.DictWriter(output, fieldnames=output_fields)
			writer.writeheader()
			for row in rows:
				row["width"], row["height"] = dimensions(row.get(dimension_column, ""))
				row.pop(dimension_column, None)
				writer.writerow(row)
		os.replace(temporary_name, path)
	except Exception:
		os.unlink(temporary_name)
		raise
	return True


def main() -> None:
	default_folder = Path(__file__).resolve().parents[2] / "test-result"
	parser = argparse.ArgumentParser(
		description="Split tuple-form image dimensions in result CSV files."
	)
	parser.add_argument(
		"folder",
		nargs="?",
		type=Path,
		default=default_folder,
		help="Test-result folder (defaults to test/test-result)",
	)
	args = parser.parse_args()
	if not args.folder.is_dir():
		parser.error(f"not a directory: {args.folder}")

	processed = sum(process_csv(path) for path in args.folder.rglob("*.csv"))
	print(f"Updated {processed} CSV file(s).")


if __name__ == "__main__":
	main()

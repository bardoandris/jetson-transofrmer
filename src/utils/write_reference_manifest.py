"""Write the fixed reference images selected for a benchmark and their hashes."""
import argparse
import csv
import hashlib
from pathlib import Path

from prompt_preparation import fixed_example_images_for_folder


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["product", "category", "reference_image", "sha256"])
        for product in ("bottle", "transistor", "cable"):
            test_root = args.dataset / product / "test"
            for category, image in fixed_example_images_for_folder(str(test_root)):
                digest = hashlib.sha256(image.read_bytes()).hexdigest()
                writer.writerow([product, category, str(image), digest])


if __name__ == "__main__":
    main()

import argparse
import json
from itertools import product
from typing import Any

import run_inference


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run inference across folder, resolution, and prompt combinations."
    )
    parser.add_argument(
        "-f",
        "--folder",
        action="append",
        required=True,
        help="Image directory; repeat this option to test multiple directories.",
    )
    parser.add_argument(
        "-r",
        "--resolution",
        action="append",
        required=True,
        type=int,
        help="Largest image dimension after downscaling; repeat to test multiple resolutions.",
    )
    parser.add_argument(
        "-p",
        "--prompt-file",
        action="append",
        required=True,
        help="Prompt file; repeat to test multiple prompts.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="scaffold_test_results.json",
        help="Path to the JSON file where scenario results will be saved.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    scenarios: list[dict[str, Any]] = []

    for folder, resolution, prompt_file in product(
        args.folder, args.resolution, args.prompt_file
    ):
        results = run_inference.run_inference(folder, resolution, prompt_file)
        scenarios.append(
            {
                "metadata": {
                    "folder": folder,
                    "resolution": resolution,
                    "prompt_file": prompt_file,
                },
                "results": results,
            }
        )

    with open(args.output, "w", encoding="utf-8") as output_file:
        json.dump(scenarios, output_file, indent=2)
        output_file.write("\n")


if __name__ == "__main__":
    main()
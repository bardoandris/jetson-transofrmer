import argparse
import csv
import json
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
        "-m",
        "--model",
        help="Model ID to use; defaults to the first model available from the API.",
    )
    parser.add_argument(
        "--power-mode",
        required=True,
        help="Power mode used during inference.",
    )
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument(
        "-o",
        "--json",
        "--output",
        dest="json_output",
        metavar="FILE",
        help="Path to the JSON file where scenario results will be saved.",
    )
    output_group.add_argument(
        "--csv",
        dest="csv_output",
        metavar="FILE",
        help="Path to the CSV file where image results will be saved.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    model = run_inference.choose_model(args.model)
    scenarios: list[dict[str, Any]] = []

    for prompt_file in args.prompt_file:
        with open(prompt_file, encoding="utf-8") as prompt_file_handle:
            prompt = prompt_file_handle.read()
        inference = run_inference.RunInference(
            prompt,
            model,
            run_inference.prompt_uses_one_shot_examples(prompt_file),
        )
        for folder in args.folder:
            inference.add_folder(folder)
        for resolution in args.resolution:
            inference.add_resolution(resolution)
        for scenario in inference.run_inference():
            scenarios.append(
                {
                    "metadata": {
                        "case_label": os.path.basename(
                            os.path.normpath(scenario["folder"])
                        ),
                        "resolution": scenario["resolution"],
                        "prompt_file": prompt_file,
                        "model": model,
                    },
                    "results": scenario["results"],
                }
            )

    if args.csv_output is not None:
        fieldnames = [
            "case_label",
            "resolution",
            "prompt_file",
            "model",
            "power_mode",
            "shot_mode",
            "image_path",
            "response",
            "inference_time",
            "processing_time",
            "width",
            "height",
        ]
        with open(args.csv_output, "w", encoding="utf-8", newline="") as output_file:
            writer = csv.DictWriter(output_file, fieldnames=fieldnames)
            writer.writeheader()
            for scenario in scenarios:
                metadata = scenario["metadata"]
                for result in scenario["results"]:
                    writer.writerow(
                        {
                            **metadata,
                            "power_mode": args.power_mode,
                            "shot_mode": (
                                "one-shot"
                                if run_inference.prompt_uses_one_shot_examples(
                                    metadata["prompt_file"]
                                )
                                else "zero-shot"
                            ),
                            **result,
                        }
                    )
    else:
        output_path = (
            args.json_output
            if args.json_output is not None
            else "scaffold_test_results.json"
        )
        with open(output_path, "w", encoding="utf-8") as output_file:
            json.dump(scenarios, output_file, indent=2)
            output_file.write("\n")


if __name__ == "__main__":
    main()
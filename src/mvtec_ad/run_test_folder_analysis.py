import argparse
import csv
import json
from pathlib import Path

import run_inference


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run folder tests and write per-image analysis results to CSV."
    )
    parser.add_argument(
        "-f",
        "--folder",
        action="append",
        required=True,
        help="Category image directory; repeat this option to test multiple categories.",
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
        help="Prompt file; repeat this option to test multiple prompts.",
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
    parser.add_argument(
        "--csv",
        required=True,
        metavar="FILE",
        help="Path to the CSV file where per-image analysis results will be saved.",
    )
    return parser.parse_args()


def build_analysis_row(
    folder: str,
    resolution: int,
    prompt_file: str,
    model: str,
    power_mode: str,
    result: run_inference.InferenceResult,
) -> dict[str, str | int]:
    response_text = result["response"]
    if not isinstance(response_text, str):
        raise TypeError(f"Expected a string response for {result['image_path']}.")
    response_data = json.loads(response_text)
    answer_category = response_data["defect_category"]
    if not isinstance(answer_category, str):
        raise TypeError(
            f"Expected a string defect_category for {result['image_path']}."
        )

    return {
        "true_category": Path(folder).name,
        "test_image": result["image_path"],
        "processing_time": result["processing_time"],
        "request_time": result["inference_time"],
        "answer_category": answer_category,
        "width": result["width"],
        "height": result["height"],
        "prompt_file": Path(prompt_file).name,
        "resolution": resolution,
        "model": model,
        "power_mode": power_mode,
        "shot_mode": (
            "one-shot"
            if run_inference.prompt_uses_one_shot_examples(prompt_file)
            else "zero-shot"
        ),
    }


def write_results_csv(
    output_path: str,
    scenarios: list[tuple[str, int, str, list[run_inference.InferenceResult]]],
    model: str,
    power_mode: str,
) -> None:
    fieldnames = [
        "true_category",
        "test_image",
        "processing_time",
        "request_time",
        "answer_category",
        "width",
        "height",
        "prompt_file",
        "resolution",
        "model",
        "power_mode",
        "shot_mode",
    ]

    with open(output_path, "w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        writer.writeheader()
        for folder, resolution, prompt_file, results in scenarios:
            for result in results:
                writer.writerow(
                    build_analysis_row(
                        folder, resolution, prompt_file, model, power_mode, result
                    )
                )


def main() -> None:
    args = parse_args()
    model = run_inference.choose_model(args.model)
    scenarios: list[tuple[str, int, str, list[run_inference.InferenceResult]]] = []
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
                (
                    scenario["folder"],
                    scenario["resolution"],
                    prompt_file,
                    scenario["results"],
                )
            )
    write_results_csv(args.csv, scenarios, model, args.power_mode)


if __name__ == "__main__":
    main()

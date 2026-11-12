import argparse
import csv
import json
import os
from pathlib import Path

from openai import OpenAI

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
        help="Model ID to use; choose from available models if omitted.",
    )
    parser.add_argument(
        "--csv",
        required=True,
        metavar="FILE",
        help="Path to the CSV file where per-image analysis results will be saved.",
    )
    return parser.parse_args()


def choose_model(model: str | None = None) -> str:
    if model is not None:
        if not model:
            raise ValueError("Model ID must not be empty.")
        return model

    base_url = os.getenv("OPENAI_BASE_URL", "http://localhost:8080/v1")
    api_key = os.getenv("OPENAI_API_KEY", "ollama")
    available_models = OpenAI(base_url=base_url, api_key=api_key).models.list().data
    if not available_models:
        raise RuntimeError(f"No models are available from the API at {base_url}.")

    print("Available models:")
    for index, available_model in enumerate(available_models, start=1):
        print(f"{index}. {available_model.id}")

    while True:
        choice = input("Choose a model by number: ")
        try:
            model_index = int(choice) - 1
        except ValueError:
            print("Enter a number from the list.")
            continue
        if 0 <= model_index < len(available_models):
            return available_models[model_index].id
        print(f"Choose a number between 1 and {len(available_models)}.")


def build_analysis_row(
    folder: str,
    resolution: int,
    prompt_file: str,
    model: str,
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
    }


def write_results_csv(
    output_path: str,
    scenarios: list[tuple[str, int, str, list[run_inference.InferenceResult]]],
    model: str,
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
    ]

    with open(output_path, "w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        writer.writeheader()
        for folder, resolution, prompt_file, results in scenarios:
            for result in results:
                writer.writerow(
                    build_analysis_row(folder, resolution, prompt_file, model, result)
                )


def main() -> None:
    args = parse_args()
    model = choose_model(args.model)
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
    write_results_csv(args.csv, scenarios, model)


if __name__ == "__main__":
    main()

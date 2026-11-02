import argparse
import json
import os
from itertools import product
from typing import Any

from openai import OpenAI

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
        help="Model ID to use; choose from available models if omitted.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="scaffold_test_results.json",
        help="Path to the JSON file where scenario results will be saved.",
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


def main() -> None:
    args = parse_args()
    model = choose_model(args.model)
    scenarios: list[dict[str, Any]] = []

    for folder, resolution, prompt_file in product(
        args.folder, args.resolution, args.prompt_file
    ):
        results = run_inference.run_inference(
            folder, resolution, prompt_file, model
        )
        scenarios.append(
            {
                "metadata": {
                    "folder": folder,
                    "resolution": resolution,
                    "prompt_file": prompt_file,
                    "model": model,
                },
                "results": results,
            }
        )

    with open(args.output, "w", encoding="utf-8") as output_file:
        json.dump(scenarios, output_file, indent=2)
        output_file.write("\n")


if __name__ == "__main__":
    main()
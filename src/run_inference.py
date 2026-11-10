import argparse
import base64
import csv
import io
import json
import os
import sys
from typing import TypedDict

import PIL
import PIL.Image
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

import utils.timer_ctx.timer_ctx as timer_ctx
import utils.vlm_schemas as vlm_schemas


class InferenceResult(TypedDict):
    image_path: str
    response: str
    inference_time: str
    processing_time: str
    width: int
    height: int


class InferenceScenario(TypedDict):
    folder: str
    resolution: int
    results: list[InferenceResult]


class HelpArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_help(sys.stderr)
        self.exit(2, f"{self.prog}: error: {message}\n")


def parse_args() -> argparse.Namespace:
    parser = HelpArgumentParser(description="Run the VLM image script.")
    parser.add_argument(
        "-f",
        "--folder",
        required=True,
        type=str,
        help="Path to the directory containing images",
    )
    parser.add_argument(
        "-r",
        "--resolution",
        required=True,
        type=int,
        help="Largest image dimension after downscaling",
    )
    parser.add_argument(
        "-p",
        "--prompt-file",
        required=True,
        type=str,
        help="Path to the file containing the VLM prompt",
    )
    parser.add_argument(
        "-m",
        "--model",
        required=True,
        type=str,
        help="Model ID to use for inference",
    )
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument(
        "--json",
        dest="json_output",
        metavar="FILE",
        help="Path to the JSON file where inference results will be saved.",
    )
    output_group.add_argument(
        "--csv",
        metavar="FILE",
        help="Path to the CSV file where inference results will be saved.",
    )
    return parser.parse_args()


def load_image(image_path: str, resolution: int = 0) -> PIL.Image.Image:
    """
    Loads the image and optionally scales it while maintaining aspect ratio.
    """
    with PIL.Image.open(image_path) as img:
        if resolution != 0:
            img.thumbnail((resolution, resolution), PIL.Image.Resampling.BICUBIC)
        return img


class RunInference:
    def __init__(self, prompt: str, model: str):
        if not model:
            raise ValueError("model must not be empty.")
        self.prompt = prompt
        self.model = model
        self.folders: list[str] = []
        self.resolutions: list[int] = []
        base_url = os.getenv("OPENAI_BASE_URL", "http://localhost:8080/v1")
        api_key = os.getenv("OPENAI_API_KEY", "ollama")
        self.client = OpenAI(base_url=base_url, api_key=api_key)

    def add_folder(self, folder: str) -> None:
        if folder not in self.folders:
            self.folders.append(folder)

    def add_resolution(self, resolution: int) -> None:
        if resolution < 0:
            raise ValueError("resolution must be zero or a positive integer.")
        if resolution not in self.resolutions:
            self.resolutions.append(resolution)

    def create_messages(self, image_data: str) -> list[ChatCompletionMessageParam]:
        return [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"{self.prompt}\n\n"
                            "Return a JSON object matching this schema:\n"
                            f"{json.dumps(vlm_schemas.category_schema)}"
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_data}"
                        },
                    },
                ],
            }
        ]

    def run_inference(self) -> list[InferenceScenario]:
        if not self.folders:
            raise ValueError("Add at least one folder before running inference.")
        if not self.resolutions:
            raise ValueError("Add at least one resolution before running inference.")

        scenarios: list[InferenceScenario] = []
        for folder in self.folders:
            if not os.path.isdir(folder):
                raise ValueError(f"Provided folder path '{folder}' is not a directory.")
            filelist = [
                os.path.join(folder, file)
                for file in os.listdir(folder)
                if file.lower().endswith((".png", ".jpg", ".jpeg"))
            ]

            for resolution in self.resolutions:
                results: list[InferenceResult] = []
                print(
                    "beginning processing"
                    + f" with model: {self.model}"
                    + "@resolution: "
                    + str(resolution)
                )
                for image_path in filelist:
                    processing_timer = timer_ctx.Timer()
                    inference_timer = timer_ctx.Timer()
                    with processing_timer:
                        image = load_image(image_path, resolution)
                        image_buffer = io.BytesIO()
                        image.save(image_buffer, format="jpeg")
                        image_base64 = base64.b64encode(
                            image_buffer.getvalue()
                        ).decode("utf-8")
                    with inference_timer:
                        response = self.client.chat.completions.create(
                            model=self.model,
                            messages=self.create_messages(image_base64),
                            response_format={
                                "type": "json_schema",
                                "json_schema": {
                                    "name": "category",
                                    "strict": True,
                                    "schema": vlm_schemas.category_schema,
                                },
                            },
                            temperature=0,
                        )
                    response_text = str(response.choices[0].message.content)
                    width, height = image.size
                    results.append(
                        {
                            "image_path": image_path,
                            "response": (
                                response_text.replace("\r\n", " ")
                                .replace("\r", " ")
                                .replace("\n", " ")
                            ),
                            "inference_time": str(inference_timer.elapsed_time),
                            "processing_time": str(processing_timer.elapsed_time),
                            "width": width,
                            "height": height,
                        }
                    )

                scenarios.append(
                    {"folder": folder, "resolution": resolution, "results": results}
                )
        return scenarios


def main() -> None:
    args = parse_args()
    with open(args.prompt_file, encoding="utf-8") as prompt_file_handle:
        prompt = prompt_file_handle.read()
    inference = RunInference(prompt, args.model)
    inference.add_folder(args.folder)
    inference.add_resolution(args.resolution)
    results = inference.run_inference()[0]["results"]

    if args.json_output is not None:
        with open(args.json_output, "w", encoding="utf-8") as output_file:
            json.dump(results, output_file, indent=2)
            output_file.write("\n")
    elif args.csv is not None:
        fieldnames = [
            "image_path",
            "response",
            "inference_time",
            "processing_time",
            "width",
            "height",
        ]
        with open(args.csv, "w", encoding="utf-8", newline="") as output_file:
            writer = csv.DictWriter(output_file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)


if __name__ == "__main__":
    main()

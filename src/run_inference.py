import argparse
import base64
import csv
import io
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import TypedDict

import PIL
import PIL.Image
from openai import OpenAI
from openai.types.chat import ChatCompletionContentPartParam, ChatCompletionMessageParam

import utils.timer_ctx.timer_ctx as timer_ctx
import utils.vlm_schemas as vlm_schemas


THERMAL_LIMIT_C = 70.0
THERMAL_CHECK_INTERVAL_SECONDS = 30
THERMAL_MONITOR_SCRIPT = (
    Path(__file__).resolve().parents[1] / "conf" / "tegra-thermal.sh"
)
THERMAL_ZONES_DIR = Path("/sys/devices/virtual/thermal")


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
        nargs="+",
        type=str,
        help="Path(s) to directory containing images",
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
        type=str,
        help="Model ID to use; defaults to the first model available from the API",
    )
    parser.add_argument(
        "--power-mode",
        required=True,
        type=str,
        help="Power mode used during inference",
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
    with PIL.Image.open(image_path) as source:
        img = source.convert("RGB")
        if resolution != 0:
            img.thumbnail((resolution, resolution), PIL.Image.Resampling.BICUBIC)
    return img


def encode_pil_jpeg_b64(image: PIL.Image.Image) -> str:
    image_buffer = io.BytesIO()
    image.save(image_buffer, format="jpeg", quality=90)
    return base64.b64encode(image_buffer.getvalue()).decode("ascii")


def make_dummy_jpeg_b64() -> str:
    img = PIL.Image.new("RGB", (16, 16), color=(0, 0, 0))
    return encode_pil_jpeg_b64(img)


def prompt_uses_one_shot_examples(prompt_file: str) -> bool:
    return Path(prompt_file).stem.endswith("_oneshot")


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

    selected_model = available_models[0].id
    print(f"Using available model: {selected_model}")
    return selected_model


def read_system_temperature() -> float:
    # Fast sysfs read (avoids spawning bash subprocess on every image)
    if THERMAL_ZONES_DIR.is_dir():
        temps_c: list[float] = []
        for temp_file in THERMAL_ZONES_DIR.glob("thermal_zone*/temp"):
            try:
                raw = temp_file.read_text(encoding="utf-8").strip()
                val = float(raw)
                if val > 1000.0:
                    val /= 1000.0
                if math.isfinite(val):
                    temps_c.append(val)
            except OSError:
                continue
        if temps_c:
            return max(temps_c)

    try:
        result = subprocess.run(
            ["bash", str(THERMAL_MONITOR_SCRIPT), "--once"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise RuntimeError("Unable to read the system temperature.") from error

    temperature = float(result.stdout.strip())
    if not math.isfinite(temperature):
        raise RuntimeError(f"Non-finite temperature: {temperature!r}")
    return temperature


def wait_for_safe_temperature() -> None:
    temperature = read_system_temperature()
    while temperature > THERMAL_LIMIT_C:
        print(
            f"System temperature is {temperature:.1f}C; "
            f"pausing inference until it is at or below {THERMAL_LIMIT_C:.0f}C."
        )
        time.sleep(THERMAL_CHECK_INTERVAL_SECONDS)
        temperature = read_system_temperature()


def find_test_root(folder: str) -> Path | None:
    folder_path = Path(folder).resolve()
    for candidate in (folder_path, *folder_path.parents):
        if candidate.name == "test":
            return candidate
    return None


def category_schema_for_folder(folder: str) -> dict:
    test_root = find_test_root(folder)
    if test_root is None:
        return vlm_schemas.category_schema

    categories = sorted(
        path.name for path in test_root.iterdir() if path.is_dir() and path.name != "good"
    )
    if not categories:
        raise ValueError(f"No defect-category folders found in '{test_root}'.")
    return vlm_schemas.create_category_schema(categories)


def fixed_example_images_for_folder(folder: str) -> list[tuple[str, Path]]:
    """Selects a deterministic, fixed support image (index 0) per category."""
    test_root = find_test_root(folder)
    if test_root is None:
        raise ValueError(
            f"One-shot examples require an image folder under a MVTec-AD test directory: '{folder}'."
        )

    category_directories = sorted(
        (path for path in test_root.iterdir() if path.is_dir()),
        key=lambda path: path.name,
    )
    if not category_directories:
        raise ValueError(f"No test-category folders found in '{test_root}'.")

    example_images: list[tuple[str, Path]] = []
    for category_directory in category_directories:
        image_paths = sorted(
            (
                path
                for path in category_directory.iterdir()
                if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg"}
            ),
            key=lambda path: path.name,
        )
        if not image_paths:
            raise ValueError(f"No images found in '{category_directory}'.")
        example_images.append((category_directory.name, image_paths[0].resolve()))
    return example_images


class RunInference:
    def __init__(self, prompt: str, model: str, one_shot: bool = False):
        if not model:
            raise ValueError("model must not be empty.")
        self.prompt = prompt
        self.model = model
        self.one_shot = one_shot
        self.folders: list[str] = []
        self.resolutions: list[int] = []
        self._encoded_example_cache: dict[tuple[str, int], str] = {}
        self._warmed_prefix_key: tuple[str, int] | None = None
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

    def encode_example(self, image_path: Path, resolution: int) -> str:
        cache_key = (str(image_path.resolve()), resolution)
        if cache_key not in self._encoded_example_cache:
            image = load_image(str(image_path), resolution)
            self._encoded_example_cache[cache_key] = encode_pil_jpeg_b64(image)
        return self._encoded_example_cache[cache_key]

    def build_static_user_prefix(
        self,
        example_images: list[tuple[str, str]] | None,
    ) -> list[ChatCompletionContentPartParam]:
        """Builds the byte-identical prefix shared across all query images."""
        prefix_content: list[ChatCompletionContentPartParam] = []
        if self.one_shot:
            if not example_images:
                raise ValueError("One-shot inference requires labeled example images.")
            prefix_content.append(
                {
                    "type": "text",
                    "text": "Use these labeled reference images as examples when classifying the query image.",
                }
            )
            for label, example_data in example_images:
                prefix_content.extend(
                    [
                        {
                            "type": "text",
                            "text": f"--- START OF EXAMPLE IMAGE: [{label}] ---",
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{example_data}"
                            },
                        },
                    ]
                )

        prefix_content.append(
            {
                "type": "text",
                "text": "Classify the query image according to the required JSON schema.",
            }
        )
        return prefix_content

    def request_completion(
        self,
        static_user_prefix: list[ChatCompletionContentPartParam],
        query_image_b64: str,
        category_schema: dict,
        max_tokens: int = 64,
    ) -> tuple[str, dict]:
        messages: list[ChatCompletionMessageParam] = [
            {
                "role": "system",
                "content": self.prompt,
            },
            {
                "role": "user",
                "content": [
                    *static_user_prefix,
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{query_image_b64}"
                        },
                    },
                ],
            },
        ]
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "category",
                    "strict": True,
                    "schema": category_schema,
                },
            },
            temperature=0,
            max_tokens=max_tokens,
            extra_body={
                "cache_prompt": True,
                "id_slot": 0,
            },
        )
        raw = response.model_dump()
        timings = raw.get("timings") or {}
        return str(response.choices[0].message.content), timings

    def run_inference(self) -> list[InferenceScenario]:
        if not self.folders:
            raise ValueError("Add at least one folder before running inference.")
        if not self.resolutions:
            raise ValueError("Add at least one resolution before running inference.")

        scenarios: list[InferenceScenario] = []
        dummy_b64 = make_dummy_jpeg_b64()

        for resolution in self.resolutions:
            for folder in self.folders:
                if not os.path.isdir(folder):
                    raise ValueError(f"Provided folder path '{folder}' is not a directory.")

                test_root = find_test_root(folder)
                prefix_scope = str(test_root) if test_root is not None else str(Path(folder).resolve())
                category_schema = category_schema_for_folder(folder)

                support_paths: set[Path] = set()
                encoded_examples: list[tuple[str, str]] | None = None
                if self.one_shot:
                    fixed_examples = fixed_example_images_for_folder(folder)
                    support_paths = {path for _, path in fixed_examples}
                    encoded_examples = [
                        (label, self.encode_example(path, resolution))
                        for label, path in fixed_examples
                    ]

                static_user_prefix = self.build_static_user_prefix(encoded_examples)

                filelist = sorted(
                    os.path.join(folder, file)
                    for file in os.listdir(folder)
                    if file.lower().endswith((".png", ".jpg", ".jpeg"))
                    and Path(folder, file).resolve() not in support_paths
                )

                results: list[InferenceResult] = []
                print(
                    f"beginning processing folder={folder} model={self.model} @resolution={resolution}"
                )

                # Pre-warm Slot 0 once per (test_root, resolution) with a 1-token dummy query
                prefix_key = (prefix_scope, resolution)
                if filelist and self._warmed_prefix_key != prefix_key:
                    print("pre-warming KV prefix cache in slot 0...")
                    wait_for_safe_temperature()
                    _, warm_timings = self.request_completion(
                        static_user_prefix,
                        dummy_b64,
                        category_schema,
                        max_tokens=1,
                    )
                    print(
                        f"warmup complete (prompt_n={warm_timings.get('prompt_n')}, "
                        f"cache_n={warm_timings.get('cache_n')})"
                    )
                    self._warmed_prefix_key = prefix_key

                for image_path in filelist:
                    processing_timer = timer_ctx.Timer()
                    inference_timer = timer_ctx.Timer()
                    with processing_timer:
                        image = load_image(image_path, resolution)
                        image_base64 = encode_pil_jpeg_b64(image)
                        width, height = image.size

                    wait_for_safe_temperature()
                    with inference_timer:
                        response_text, timings = self.request_completion(
                            static_user_prefix,
                            image_base64,
                            category_schema,
                            max_tokens=64,
                        )

                    print(
                        f"{Path(image_path).name}: {inference_timer.elapsed_time:.3f}s "
                        f"(cache_n={timings.get('cache_n')}, prompt_n={timings.get('prompt_n')})"
                    )
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
    model = choose_model(args.model)
    with open(args.prompt_file, encoding="utf-8") as prompt_file_handle:
        prompt = prompt_file_handle.read()
    inference = RunInference(
        prompt, model, prompt_uses_one_shot_examples(args.prompt_file)
    )
    for folder in args.folder:
        inference.add_folder(folder)
    inference.add_resolution(args.resolution)
    scenarios = inference.run_inference()
    results = [item for scenario in scenarios for item in scenario["results"]]

    if args.json_output is not None:
        with open(args.json_output, "w", encoding="utf-8") as output_file:
            json.dump(results, output_file, indent=2)
            output_file.write("\n")
    elif args.csv is not None:
        fieldnames = [
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
        with open(args.csv, "w", encoding="utf-8", newline="") as output_file:
            writer = csv.DictWriter(output_file, fieldnames=fieldnames)
            writer.writeheader()
            shot_mode = (
                "one-shot"
                if prompt_uses_one_shot_examples(args.prompt_file)
                else "zero-shot"
            )
            writer.writerows(
                {
                    "model": model,
                    "power_mode": args.power_mode,
                    "shot_mode": shot_mode,
                    **result,
                }
                for result in results
            )


if __name__ == "__main__":
    main()
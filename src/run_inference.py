import argparse
import csv
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import TypedDict

from openai import OpenAI
from openai.types.chat import ChatCompletionContentPartParam, ChatCompletionMessageParam

import utils.timer_ctx.timer_ctx as timer_ctx
from prompt_preparation import (
    PromptPreparation,
    encode_pil_jpeg_b64,
    load_image,
    make_dummy_jpeg_b64,
    prompt_uses_one_shot_examples,
)


THERMAL_ACTIVATION_C = 85.0
THERMAL_RESUME_C = 70.0
THERMAL_CHECK_INTERVAL_SECONDS = 30
THERMAL_MONITOR_SCRIPT = (
    Path(__file__).resolve().parents[1] / "conf" / "tegra-thermal.sh"
)
THERMAL_ZONES_DIR = Path("/sys/devices/virtual/thermal")


class InferenceResult(TypedDict):
    image_path: str
    response: str
    inference_time: str
    prompt_ms: float | None
    predicted_ms: float | None
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
    if temperature < THERMAL_ACTIVATION_C:
        return
    while temperature >= THERMAL_RESUME_C:
        print(
            f"System temperature is {temperature:.1f}C; "
            f"pausing inference until it falls below {THERMAL_RESUME_C:.0f}C."
        )
        time.sleep(THERMAL_CHECK_INTERVAL_SECONDS)
        temperature = read_system_temperature()




class RunInference:
    def __init__(self, prompt: str, model: str, one_shot: bool = False):
        if not model:
            raise ValueError("model must not be empty.")
        self.prompt = prompt
        self.model = model
        self.one_shot = one_shot
        self.folders: list[str] = []
        self.resolutions: list[int] = []
        self.preparation = PromptPreparation(one_shot)
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

    def request_completion(
        self,
        static_user_prefix: list[ChatCompletionContentPartParam],
        query_image_b64: str,
        category_schema: dict,
        max_tokens: int = 2048,
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

                category_schema, static_user_prefix, filelist, prefix_key = (
                    self.preparation.prepare(folder, resolution)
                )

                results: list[InferenceResult] = []
                print(
                    f"beginning processing folder={folder} model={self.model} @resolution={resolution}"
                )

                # Pre-warm Slot 0 once per (test_root, resolution) with a 1-token dummy query
                if self.preparation.needs_warmup(prefix_key, filelist):
                    print("pre-warming KV prefix cache in slot 0...")
                    wait_for_safe_temperature()
                    _, warm_timings = self.request_completion(
                        static_user_prefix,
                        dummy_b64,
                        category_schema,
                        max_tokens=16,
                    )
                    print(
                        f"warmup complete (prompt_n={warm_timings.get('prompt_n')}, "
                        f"cache_n={warm_timings.get('cache_n')})"
                    )
                    self.preparation.mark_warmed(prefix_key)

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
                            max_tokens=2048,
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
                            "prompt_ms": timings.get("prompt_ms"),
                            "predicted_ms": timings.get("predicted_ms"),
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
            "prompt_ms",
            "predicted_ms",
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
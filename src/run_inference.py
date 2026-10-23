from uuid import uuid4

import PIL
import PIL.Image
import argparse
import sys
import os
import base64
import io
import json
from openai import OpenAI
import utils.timer_ctx.timer_ctx as timer_ctx
import utils.vlm_schemas as vlm_schemas


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
    return parser.parse_args()


def load_image(image_path: str, resolution: int = 0) -> PIL.Image.Image:
    """
    Loads the image and optionally scales it while maintaining aspect ratio.
    """
    with PIL.Image.open(image_path) as img:
        if resolution != 0:
            img.thumbnail((resolution, resolution), PIL.Image.Resampling.BICUBIC)
        return img


def run_inference(
    folder: str | None = None,
    resolution: int | None = None,
    prompt_file: str | None = None,
) -> list[dict[str, str]]:
    if __name__ == "__main__":
        args = parse_args()
        folder = args.folder
        resolution = args.resolution
        prompt_file = args.prompt_file

    if folder is None or resolution is None or prompt_file is None:
        raise ValueError(
            "folder, resolution, and prompt_file must be provided together."
        )
    results = []
    processing_timer = timer_ctx.Timer()
    inference_timer = timer_ctx.Timer()

    prompt = ""
    # open images and prompt file, check if folder exists and is a directory
    with open(prompt_file, encoding="utf-8") as prompt_file_handle:
        prompt = prompt_file_handle.read()

        if not os.path.isdir(folder):
            raise ValueError(
                f"Provided folder path '{folder}' is not a directory."
            )
        filelist = [
            f"{folder}/{file}"
            for file in os.listdir(folder)
            if file.lower().endswith((".png", ".jpg", ".jpeg"))
        ]

    base_url = os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
    api_key = os.getenv("OPENAI_API_KEY", "ollama")
    client = OpenAI(base_url=base_url, api_key=api_key)
    server_model_name = os.getenv("OPENAI_MODEL")
    if server_model_name is None:
        available_models = client.models.list().data
        if not available_models:
            raise RuntimeError(f"No models are available from the API at {base_url}.")
        server_model_name = available_models[0].id

    print("beginning processing" + f" with model: {server_model_name}"
           + "@resolution: " + str(resolution))
    for image_path in filelist:
        #image processing
        with processing_timer:
                    image = load_image(image_path, resolution)
                    image_buffer = io.BytesIO()
                    image.save(image_buffer, format="jpeg")
                    image_base64 = base64.b64encode(image_buffer.getvalue()).decode("utf-8")
        with inference_timer:
            response = client.chat.completions.create(
                model=server_model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    f"{uuid4()}\n{prompt}\n\n"
                                    "Return a JSON object matching this schema:\n"
                                    f"{json.dumps(vlm_schemas.category_schema)}"
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                },
                            },
                        ],
                    }
                ],
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
        results.append({"image_path": image_path, 
                        "response": str(response.choices[0].message.content),
                        "inference_time": inference_timer.elapsed_time.__str__(),
                        "processing_time": processing_timer.elapsed_time.__str__(),
                        "image_size": image.size.__str__()})
        del image, image_base64, response

    return results

if __name__ == "__main__":
    run_inference()

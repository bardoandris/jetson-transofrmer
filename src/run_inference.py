import PIL
import PIL.Image
import argparse
import ollama
import sys
import os
import base64
import io
import utils.timer_ctx.timer_ctx as timer_ctx
import utils.vlm_schemas as vlm_schemas
import json


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

    client = ollama.Client(host="localhost")
    server_model_name = client.list().models[0].model or ""
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
            response = client.chat(
            model=server_model_name,
            messages=[
                {
                    "role": "user",
                    "content": f"{prompt}\
                         return text in the following schema: {vlm_schemas.category_schema}",
                    "images": [image_base64]
                }
            ],
            format=vlm_schemas.category_schema,
            options={"temperature": 0, "num_ctx": 4096},
            )
        results.append({"image_path": image_path, 
                        "response": response.message.content.__str__(), 
                        "inference_time": inference_timer.elapsed_time.__str__(),
                        "processing_time": processing_timer.elapsed_time.__str__(),
                        "image_size": image.size.__str__()})
        del image, image_base64, response

    return results

if __name__ == "__main__":
    run_inference()

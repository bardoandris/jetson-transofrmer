import PIL
import PIL.Image
import argparse
import ollama
import sys
import os
import base64
import io
import utils.timer_ctx.timer_ctx as timer_ctx



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
        return img.copy()


def main():
    args = parse_args()
    prompt = ""
    # open images and prompt file, check if folder exists and is a directory
    with open(args.prompt_file, encoding="utf-8") as prompt_file:
        prompt = prompt_file.read()

        if not os.path.isdir(args.folder):
            raise ValueError(
                f"Provided folder path '{args.folder}' is not a directory."
            )
        filelist = [
            f"{args.folder}/{file}"
            for file in os.listdir(args.folder)
            if file.lower().endswith((".png", ".jpg", ".jpeg"))
        ]
    client = ollama.Client(host="localhost", port=11434)
    server_model_name = client.list().models[0].model or ""
    print("beginning processing")
    for image_path in filelist:
        image = load_image(image_path, args.resolution)
        image_buffer = io.BytesIO()
        image.save(image_buffer, format="PNG")
        image_base64 = base64.b64encode(image_buffer.getvalue()).decode("utf-8")

        response = client.generate(
            model=server_model_name,
            prompt=f"{prompt}\n \
            Return the answer in JSON format with keys 'answer' and 'confidence'.",
            images=[image_base64]
        )
        print(f"Response for {image_path}: {response.response}")


if __name__ == "__main__":
    main()

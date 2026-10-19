import PIL
import PIL.Image
import argparse
import typing
import time
import sys
import os
import base64
import utils.timer_ctx as tctx


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
        "-m", "--model", required=True, type=str, help="Name of the VLM model to use"
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
    print("beginning processing")
    for image_path in filelist:
        image = load_image(image_path, args.resolution)
        # Here you would typically process the image and prompt with the model
        # For demonstration, we will just print the image size and prompt length
        print(
            f"Processing image: {image_path}, size: {image.size}, prompt length: {
                len(prompt)
            }"
        )


if __name__ == "__main__":
    main()

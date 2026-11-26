"""Prepare category schemas, reference images, and reusable prompt prefixes."""

import base64
import io
import os
from pathlib import Path

import PIL.Image
from openai.types.chat import ChatCompletionContentPartParam

import utils.vlm_schemas as vlm_schemas


def load_image(image_path: str, resolution: int = 0) -> PIL.Image.Image:
    return load_image_with_original_size(image_path, resolution)[0]


def load_image_with_original_size(image_path: str, resolution: int = 0) -> tuple[PIL.Image.Image, tuple[int, int]]:
    with PIL.Image.open(image_path) as source:
        original_size = source.size
        img = source.convert("RGB")
        if resolution != 0:
            img.thumbnail((resolution, resolution), PIL.Image.Resampling.BICUBIC)
    return img, original_size


def encode_pil_jpeg_b64(image: PIL.Image.Image) -> str:
    image_buffer = io.BytesIO()
    image.save(image_buffer, format="jpeg", quality=90)
    return base64.b64encode(image_buffer.getvalue()).decode("ascii")


def make_dummy_jpeg_b64() -> str:
    img = PIL.Image.new("RGB", (16, 16), color=(0, 0, 0))
    return encode_pil_jpeg_b64(img)


def prompt_uses_one_shot_examples(prompt_file: str, shot_mode: str | None = None) -> bool:
    """Resolve explicit shot mode or fall back to the prompt naming convention."""
    if shot_mode is not None:
        if shot_mode not in ("one", "zero"):
            raise ValueError("Shot mode must be one or zero.")
        return shot_mode == "one"
    return Path(prompt_file).stem.endswith("_oneshot")


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


class PromptPreparation:
    def __init__(self, one_shot: bool, exclude_reference_images: bool = False):
        self.one_shot = one_shot
        self.exclude_reference_images = exclude_reference_images
        self._encoded_example_cache: dict[tuple[str, int], str] = {}
        self._warmed_prefix_key: tuple[str, int] | None = None

    def _encode_example(self, image_path: Path, resolution: int) -> str:
        cache_key = (str(image_path.resolve()), resolution)
        if cache_key not in self._encoded_example_cache:
            image = load_image(str(image_path), resolution)
            self._encoded_example_cache[cache_key] = encode_pil_jpeg_b64(image)
        return self._encoded_example_cache[cache_key]

    def _build_static_user_prefix(
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

    def prepare(
        self, folder: str, resolution: int
    ) -> tuple[dict, list[ChatCompletionContentPartParam], list[str], tuple[str, int]]:
        test_root = find_test_root(folder)
        scope = str(test_root) if test_root is not None else str(Path(folder).resolve())
        schema = category_schema_for_folder(folder)
        support_paths: set[Path] = set()
        examples = None
        if self.one_shot or self.exclude_reference_images:
            fixed = fixed_example_images_for_folder(folder)
            support_paths = {path for _, path in fixed}
        if self.one_shot:
            examples = [
                (label, self._encode_example(path, resolution)) for label, path in fixed
            ]
        prefix = self._build_static_user_prefix(examples)
        images = sorted(
            os.path.join(folder, name) for name in os.listdir(folder)
            if name.lower().endswith((".png", ".jpg", ".jpeg"))
            and Path(folder, name).resolve() not in support_paths
        )
        return schema, prefix, images, (scope, resolution)

    def needs_warmup(self, key: tuple[str, int], images: list[str]) -> bool:
        return bool(images) and self._warmed_prefix_key != key

    def mark_warmed(self, key: tuple[str, int]) -> None:
        self._warmed_prefix_key = key

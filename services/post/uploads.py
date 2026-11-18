"""Validation and normalization for uploaded post-template images."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps


def normalize_template(path: Path, size: tuple[int, int] = (1122, 1402)) -> None:
    """Fit an uploaded template to the renderer canvas without distorting it."""
    with Image.open(path) as source:
        source.load()
        original = source.convert("RGB")
    if original.width <= 0 or original.height <= 0:
        raise ValueError("Ảnh có kích thước không hợp lệ.")
    fitted = ImageOps.contain(original, size, method=Image.Resampling.LANCZOS)
    background = Image.new("RGB", size, original.getpixel((0, 0)))
    background.paste(fitted, ((size[0] - fitted.width) // 2, (size[1] - fitted.height) // 2))
    original.close()
    background.save(path, "PNG")


def validate_image(path: Path) -> None:
    """Decode an uploaded image fully to reject corrupt or unsupported files."""
    with Image.open(path) as image:
        image.load()

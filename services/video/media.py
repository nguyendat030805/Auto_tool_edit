"""File, image, OCR, and FFmpeg utilities shared by video services."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


def run(cmd: list[str]) -> str:
    """Run a subprocess and return stdout, reporting FFmpeg errors clearly."""
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        sys.exit(f"\n[LỖI] Lệnh thất bại:\n  {' '.join(cmd)}\n\n{res.stderr[-2500:]}")
    return res.stdout


def probe_duration(path: Path) -> float:
    """Read media duration in seconds using ffprobe."""
    out = run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(path),
    ])
    return float(out.strip())


def check_ffmpeg() -> None:
    """Exit with an actionable error if ffmpeg or ffprobe is unavailable."""
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            sys.exit(f"[LỖI] Không tìm thấy '{tool}'. Hãy cài ffmpeg và thêm vào PATH.")


def ocr_image(path: Path, lang: str) -> str:
    """Recognize comment text from an image with Tesseract."""
    try:
        import pytesseract
    except ImportError:
        sys.exit("[LỖI] Chưa có pytesseract. Hãy dùng --texts texts.txt hoặc cài: pip install pytesseract")
    img = Image.open(path).convert("RGB")
    img = img.resize((img.width * 2, img.height * 2), Image.LANCZOS)
    try:
        text = pytesseract.image_to_string(img, lang=lang)
    except pytesseract.TesseractError:
        print(f"[CẢNH BÁO] Tesseract không có ngôn ngữ '{lang}', dùng 'eng'. "
              "Cài gói 'tesseract-ocr-vie' để đọc tiếng Việt chuẩn hơn.")
        text = pytesseract.image_to_string(img, lang="eng")
    return " ".join(text.split())


def load_texts(args, images: list[Path]) -> list[str]:
    """Load narration lines from a text file or recognize them from images."""
    if args.texts:
        lines = [line.strip() for line in Path(args.texts).read_text(encoding="utf-8").splitlines() if line.strip()]
        if len(lines) != len(images):
            sys.exit(f"[LỖI] {len(images)} ảnh nhưng texts.txt có {len(lines)} dòng (bỏ qua dòng trống). Hai số phải bằng nhau.")
        return lines
    print("Không có --texts, đang OCR ảnh comment...")
    texts = [ocr_image(path, args.ocr_lang) for path in images]
    for path, text in zip(images, texts):
        print(f"  {path.name}: {text!r}")
    if any(len(text) < 3 for text in texts):
        sys.exit("[LỖI] OCR không đọc được chữ ở một số ảnh. Hãy tạo texts.txt thủ công và dùng --texts.")
    return texts


def prepare_card(src: Path, dst: Path, canvas_w: int, canvas_h: int,
                 width_ratio: float, max_h_ratio: float, radius: int = 36) -> tuple[int, int]:
    """Resize a comment image and add rounded corners and a soft shadow."""
    img = Image.open(src).convert("RGBA")
    target_w = int(canvas_w * width_ratio)
    scale = target_w / img.width
    new_w, new_h = target_w, int(img.height * scale)
    max_h = int(canvas_h * max_h_ratio)
    if new_h > max_h:
        scale = max_h / img.height
        new_w, new_h = int(img.width * scale), max_h
    img = img.resize((new_w, new_h), Image.LANCZOS)

    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, new_w - 1, new_h - 1], radius=radius, fill=255)
    img.putalpha(mask)

    pad = 50
    card = Image.new("RGBA", (new_w + pad * 2, new_h + pad * 2), (0, 0, 0, 0))
    shadow = Image.new("RGBA", card.size, (0, 0, 0, 0))
    shadow_mask = Image.new("L", card.size, 0)
    ImageDraw.Draw(shadow_mask).rounded_rectangle(
        [pad, pad + 10, pad + new_w, pad + new_h + 10], radius=radius, fill=150)
    shadow.putalpha(shadow_mask.filter(ImageFilter.GaussianBlur(18)))
    card = Image.alpha_composite(card, shadow)
    card.alpha_composite(img, (pad, pad))
    card.save(dst)
    return card.size


def parse_size(value: str) -> tuple[int, int]:
    """Parse a video resolution written as WIDTHxHEIGHT."""
    try:
        width, height = value.lower().split("x")
        return int(width), int(height)
    except ValueError:
        raise argparse.ArgumentTypeError("Kích thước phải dạng 1080x1920")

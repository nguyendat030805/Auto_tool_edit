"""Command-line entry point for generating post-template images."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .renderer import render_post


def main() -> None:
    """Parse post-template options and write the generated image."""
    parser = argparse.ArgumentParser(description="Tạo ảnh bài viết từ template (ô lớn + 0-3 comment).")
    parser.add_argument("--main", required=True, help="Nội dung bài viết chính.")
    parser.add_argument("--comment", action="append", default=[], help="Nội dung comment; có thể dùng nhiều lần.")
    parser.add_argument("--align", choices=["center", "left"], default="center")
    parser.add_argument("--template", type=Path)
    parser.add_argument("--out", type=Path, default=Path("bai_viet.png"))
    args = parser.parse_args()
    try:
        image = render_post(args.main, args.comment, args.align, args.template)
    except (FileNotFoundError, ValueError, RuntimeError) as error:
        sys.exit(f"[LỖI] {error}")
    image.save(args.out)
    print(f"Đã tạo {args.out.resolve()} ({image.width}x{image.height})")

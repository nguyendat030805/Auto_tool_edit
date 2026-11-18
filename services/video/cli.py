"""Command-line orchestration for video creation."""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from .audio import SFX_STYLES, build_audio, make_sfx, mix_bgm, mix_sfx
from .media import check_ffmpeg, load_texts, parse_size, prepare_card, probe_duration
from .renderer import render
from .speech import TTS_ENGINES, TTSError


def main() -> None:
    """Parse CLI arguments and run the complete video-creation pipeline."""
    parser = argparse.ArgumentParser(description="Tạo video đọc comment tự động (video nền + ảnh comment + TTS).")
    parser.add_argument("--bg", required=True, type=Path, help="Video nền (mp4...). Tự lặp/cắt cho vừa độ dài.")
    parser.add_argument("--comments", required=True, nargs="+", type=Path, help="3-4 ảnh chụp comment, theo thứ tự xuất hiện.")
    parser.add_argument("--texts", type=Path, help="File txt: mỗi dòng là lời đọc của 1 comment (cùng thứ tự ảnh).")
    parser.add_argument("--audio", nargs="+", type=Path,
                        help="File âm thanh tạo sẵn, mỗi comment một file, cùng thứ tự ảnh.")
    parser.add_argument("--out", type=Path, default=Path("output.mp4"))
    parser.add_argument("--tts-engine", choices=list(TTS_ENGINES), default="auto")
    parser.add_argument("--voice", default="vi-VN-HoaiMyNeural")
    parser.add_argument("--rate", default="+0%")
    parser.add_argument("--lang", default="vi")
    parser.add_argument("--ocr-lang", default="vie+eng")
    parser.add_argument("--ocr-only", action="store_true")
    parser.add_argument("--size", type=parse_size, default=(1080, 1920))
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--gap", type=float, default=0.6)
    parser.add_argument("--lead", type=float, default=0.5)
    parser.add_argument("--tail", type=float, default=1.0)
    parser.add_argument("--sfx", type=Path)
    parser.add_argument("--sfx-style", choices=list(SFX_STYLES), default="ding")
    parser.add_argument("--sfx-volume", type=float, default=0.8)
    parser.add_argument("--no-sfx", action="store_true")
    parser.add_argument("--bgm", type=Path)
    parser.add_argument("--bgm-volume", type=float, default=0.15)
    parser.add_argument("--no-bgm-duck", action="store_true")
    parser.add_argument("--dim", type=float, default=0.25)
    parser.add_argument("--card-width", type=float, default=0.85)
    parser.add_argument("--post-image", type=Path)
    parser.add_argument("--post-text")
    parser.add_argument("--post-audio", type=Path)
    parser.add_argument("--post-gap", type=float, default=1.0)
    parser.add_argument("--post-width", type=float, default=0.94)
    parser.add_argument("--offset-y", type=int, default=0)
    parser.add_argument("--keep-temp", action="store_true")
    args = parser.parse_args()

    check_ffmpeg()
    if not args.bg.is_file():
        sys.exit(f"[LỖI] Không thấy video nền: {args.bg}")
    for comment in args.comments:
        if not comment.is_file():
            sys.exit(f"[LỖI] Không thấy ảnh: {comment}")
    if not 1 <= len(args.comments) <= 6:
        sys.exit("[LỖI] Nên dùng 3-4 ảnh comment (tối đa 6).")

    if args.ocr_only:
        from .media import ocr_image
        for comment in args.comments:
            print(ocr_image(comment, args.ocr_lang))
        return

    has_post = args.post_image is not None
    if has_post and not args.post_image.is_file():
        sys.exit(f"[LỖI] Không thấy ảnh bài viết chính: {args.post_image}")

    audio_files: list[Path] = []
    if args.audio:
        if len(args.audio) != len(args.comments):
            sys.exit(f"[LỖI] {len(args.comments)} ảnh nhưng {len(args.audio)} file audio. Hai số phải bằng nhau.")
        for audio_file in args.audio:
            if not audio_file.is_file():
                sys.exit(f"[LỖI] Không thấy file audio: {audio_file}")
        if has_post:
            if not args.post_audio or not args.post_audio.is_file():
                sys.exit("[LỖI] Có ảnh bài viết chính nhưng thiếu --post-audio (file audio đọc bài viết).")
            audio_files.append(args.post_audio)
        audio_files += list(args.audio)
        texts = []
    else:
        texts = load_texts(args, args.comments)
        if has_post:
            if not args.post_text or not args.post_text.strip():
                sys.exit("[LỖI] Có ảnh bài viết chính nhưng thiếu --post-text (lời đọc bài viết).")
            texts = [" ".join(args.post_text.split())] + texts

    def label(index: int) -> str:
        """Return the narration label used in progress and error messages."""
        return "bài viết chính" if has_post and index == 0 else (
            f"comment {index}" if has_post else f"comment {index + 1}")

    engine, extension = TTS_ENGINES[args.tts_engine]
    width, height = args.size
    workdir = Path(tempfile.mkdtemp(prefix="cmtvideo_"))
    try:
        clips, durations = [], []
        if args.audio:
            print("[1/4] Dùng file audio có sẵn...")
            for index, audio_file in enumerate(audio_files):
                clips.append(audio_file)
                durations.append(probe_duration(audio_file))
                print(f"   {label(index)}: {audio_file.name} ({durations[-1]:.1f}s)")
        else:
            print(f"[1/4] Tạo giọng đọc ({args.tts_engine})...")
            for index, text in enumerate(texts):
                clip = workdir / f"tts_{index}{extension}"
                try:
                    engine(text, clip, args)
                except TTSError as error:
                    sys.exit(f"[LỖI] Không tạo được giọng đọc cho {label(index)}: {error}\n"
                             "  Cách xử lý: cài edge-tts/gTTS, kiểm tra internet hoặc dùng file audio có sẵn.")
                if not clip.exists() or clip.stat().st_size == 0:
                    sys.exit(f"[LỖI] TTS không tạo được file cho {label(index)}.")
                clips.append(clip)
                durations.append(probe_duration(clip))
                print(f"   {label(index)}: {durations[-1]:.1f}s")

        print("[2/4] Ghép audio & tính mốc thời gian...")
        use_sfx = not args.no_sfx
        if args.sfx and not args.sfx.is_file():
            sys.exit(f"[LỖI] Không thấy file tiếng hiệu ứng: {args.sfx}")
        pads = [args.gap] * (len(clips) - 1) + [args.tail]
        if has_post and len(pads) > 1:
            pads[0] = args.post_gap
        audio, cues, total = build_audio(
            clips, durations, args.gap, args.lead, args.tail, workdir,
            voice_delay=0.35 if use_sfx else 0.0, pads=pads)
        if use_sfx:
            print("   thêm tiếng hiệu ứng khi comment xuất hiện...")
            effect = args.sfx if args.sfx else make_sfx(args.sfx_style, workdir)
            audio = mix_sfx(audio, effect, [start for start, _ in cues],
                            max(0.0, min(2.0, args.sfx_volume)), workdir)
        if args.bgm:
            if not args.bgm.is_file():
                sys.exit(f"[LỖI] Không thấy file nhạc nền: {args.bgm}")
            print("   thêm nhạc nền...")
            audio = mix_bgm(audio, args.bgm, max(0.0, min(1.0, args.bgm_volume)),
                            not args.no_bgm_duck, workdir)

        print("[3/4] Chuẩn bị ảnh comment...")
        cards, card_sizes = [], []
        if has_post:
            card = workdir / "card_post.png"
            card_sizes.append(prepare_card(args.post_image, card, width, height, args.post_width, 0.80))
            cards.append(card)
        for index, comment in enumerate(args.comments):
            card = workdir / f"card_{index}.png"
            card_sizes.append(prepare_card(comment, card, width, height, args.card_width, 0.55))
            cards.append(card)

        print(f"[4/4] Render video ({total:.1f}s)...")
        render(args, cards, card_sizes, cues, audio, total, args.out)
        print(f"\nXong! -> {args.out.resolve()}")
    finally:
        if args.keep_temp:
            print(f"(thư mục tạm: {workdir})")
        else:
            shutil.rmtree(workdir, ignore_errors=True)

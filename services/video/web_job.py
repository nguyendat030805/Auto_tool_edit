"""Job adapter that converts browser uploads into the video CLI invocation."""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VIDEO_SIZES = {"portrait": "1080x1920", "landscape": "1920x1080", "square": "1080x1080"}


def _video_command_prefix() -> list[str]:
    """Select the Python script or frozen-app entry point for video rendering."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "--video-cli"]
    return [sys.executable, str(PROJECT_ROOT / "make_video.py")]


def _clamp(value, lower, upper):
    """Keep an incoming UI option inside its allowed range."""
    return max(lower, min(upper, value))


def run_job(job: dict, opts: dict) -> None:
    """Validate a browser job, invoke the video service, and collect its logs."""
    directory: Path = job["dir"]
    log: list[str] = job["log"]

    def fail(message: str) -> None:
        """Record a user-visible error and mark the job as failed."""
        log.append(message)
        job["state"] = "error"

    try:
        count = int(opts["count"])
        background = next(iter(directory.glob("bg.*")), None)
        images = sorted(directory.glob("img_*"), key=lambda path: int(path.stem.split("_")[1]))
        if background is None or len(images) != count:
            return fail("[LỖI] Thiếu file tải lên, hãy thử lại.")

        output = directory / "output.mp4"
        command = [
            *_video_command_prefix(),
            "--bg", str(background), "--comments", *map(str, images), "--out", str(output),
            "--size", VIDEO_SIZES.get(opts.get("size"), VIDEO_SIZES["portrait"]),
            "--dim", f"{_clamp(float(opts.get('dim', 0.25)), 0, 0.8):.2f}",
            "--offset-y", str(int(_clamp(int(opts.get("offset_y", 0)), -900, 900))),
        ]

        if opts.get("bgm"):
            bgm = next(iter(directory.glob("bgm_0.*")), None)
            if bgm is None:
                return fail("[LỖI] Thiếu file nhạc nền, hãy thử lại.")
            command += ["--bgm", str(bgm),
                        "--bgm-volume", f"{_clamp(float(opts.get('bgm_volume', 0.15)), 0.0, 1.0):.2f}"]
            if not opts.get("bgm_duck", True):
                command.append("--no-bgm-duck")

        post_text = ""
        if opts.get("post"):
            post = next(iter(directory.glob("post_0.*")), None)
            if post is None:
                return fail("[LỖI] Thiếu ảnh bài viết chính, hãy thử lại.")
            command += ["--post-image", str(post)]
            post_text = " ".join(str(opts.get("post_text", "")).split())

        sfx = opts.get("sfx", "ding")
        if sfx == "none":
            command.append("--no-sfx")
        else:
            command += ["--sfx-volume", f"{_clamp(float(opts.get('sfx_volume', 0.8)), 0.0, 2.0):.2f}"]
            if sfx == "custom":
                effect = next(iter(directory.glob("sfx_0.*")), None)
                if effect is None:
                    return fail("[LỖI] Thiếu file tiếng hiệu ứng, hãy thử lại.")
                command += ["--sfx", str(effect)]
            elif sfx in ("ding", "pop", "whoosh"):
                command += ["--sfx-style", sfx]

        if opts.get("mode") == "audio":
            audio_files = sorted(directory.glob("audio_*"), key=lambda path: int(path.stem.split("_")[1]))
            if len(audio_files) != count:
                return fail("[LỖI] Số file audio không khớp số ảnh.")
            command += ["--audio", *map(str, audio_files)]
            if opts.get("post"):
                post_audio = next(iter(directory.glob("postaudio_0.*")), None)
                if post_audio is None:
                    return fail("[LỖI] Thiếu file audio đọc bài viết chính.")
                command += ["--post-audio", str(post_audio)]
        else:
            texts = [" ".join(str(text).split()) for text in opts.get("texts", [])]
            if len(texts) != count or any(not text for text in texts):
                return fail("[LỖI] Lời đọc chưa đủ cho các comment.")
            text_file = directory / "texts.txt"
            text_file.write_text("\n".join(texts) + "\n", encoding="utf-8")
            voice = str(opts.get("voice", "vi-VN-HoaiMyNeural"))
            rate = str(opts.get("rate", "+0%"))
            if not re.fullmatch(r"[A-Za-z0-9-]{3,60}", voice) or not re.fullmatch(r"[+-]\d{1,3}%", rate):
                return fail("[LỖI] Tuỳ chọn giọng đọc không hợp lệ.")
            command += ["--texts", str(text_file), "--voice", voice, "--rate", rate]
            if opts.get("post"):
                if not post_text:
                    return fail("[LỖI] Bài viết chính chưa có lời đọc.")
                command += ["--post-text", post_text]
            if opts.get("engine") in ("auto", "edge", "gtts", "pyttsx3", "beep"):
                command += ["--tts-engine", opts["engine"]]

        environment = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", env=environment, cwd=str(PROJECT_ROOT))
        assert process.stdout is not None
        for line in process.stdout:
            line = line.rstrip()
            if line:
                log.append(line)
        process.wait()
        if process.returncode == 0 and output.exists():
            job["state"] = "done"
        else:
            fail("[LỖI] Tạo video thất bại (xem thông báo ở trên).")
    except Exception as error:  # noqa: BLE001
        fail(f"[LỖI] {error}")

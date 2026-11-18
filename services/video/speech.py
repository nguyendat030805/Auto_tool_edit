"""Speech synthesis backends for narration audio."""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

from .media import run


async def _edge_tts(text: str, out: Path, voice: str, rate: str) -> None:
    """Synthesize one speech clip with Microsoft Edge TTS."""
    import edge_tts
    await edge_tts.Communicate(text, voice, rate=rate).save(str(out))


class TTSError(RuntimeError):
    """A speech backend failed with a user-facing explanation."""


_EDGE_BROKEN = False


def tts_edge(text: str, out: Path, args) -> None:
    """Generate an Edge TTS clip and retry transient failures."""
    try:
        import edge_tts  # noqa: F401
    except ImportError:
        raise TTSError("chưa cài edge-tts (pip install edge-tts)")
    last: Exception | None = None
    for _ in range(3):
        try:
            asyncio.run(_edge_tts(text, out, args.voice, args.rate))
            if out.exists() and out.stat().st_size > 0:
                return
        except Exception as e:  # noqa: BLE001
            last = e
        out.unlink(missing_ok=True)
        time.sleep(1.5)
    reason = type(last).__name__ if last else "không nhận được âm thanh"
    raise TTSError(f"edge-tts lỗi ({reason})")


def tts_gtts(text: str, out: Path, args) -> None:
    """Generate a speech clip with Google Text-to-Speech."""
    try:
        from gtts import gTTS
    except ImportError:
        raise TTSError("chưa cài gTTS (pip install gTTS)")
    try:
        gTTS(text=text, lang=args.lang).save(str(out))
    except Exception as e:  # noqa: BLE001
        raise TTSError(f"gTTS lỗi ({type(e).__name__}), kiểm tra kết nối internet")


def tts_pyttsx3(text: str, out: Path, args) -> None:
    """Generate a speech clip using the optional offline pyttsx3 backend."""
    try:
        import pyttsx3
    except ImportError:
        raise TTSError("chưa cài pyttsx3 (pip install pyttsx3)")
    engine = pyttsx3.init()
    engine.save_to_file(text, str(out))
    engine.runAndWait()


def tts_auto(text: str, out: Path, args) -> None:
    """Try Edge TTS first, then fall back to Google TTS."""
    global _EDGE_BROKEN
    if not _EDGE_BROKEN:
        try:
            tts_edge(text, out, args)
            return
        except TTSError as e:
            _EDGE_BROKEN = True
            print(f"   [!] {e}. Chuyển sang giọng Google (gTTS) cho phần còn lại.")
    tts_gtts(text, out, args)


def tts_beep(text: str, out: Path, args) -> None:
    """Generate a short test tone whose duration follows the narration length."""
    duration = max(1.0, len(text.split()) * 0.35)
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}", str(out)])


TTS_ENGINES = {
    "auto": (tts_auto, ".mp3"),
    "edge": (tts_edge, ".mp3"),
    "gtts": (tts_gtts, ".mp3"),
    "pyttsx3": (tts_pyttsx3, ".wav"),
    "beep": (tts_beep, ".wav"),
}

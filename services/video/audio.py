"""Audio assembly, effect sounds, and background music mixing."""
from __future__ import annotations

import subprocess
from pathlib import Path

from .media import probe_duration, run

SFX_STYLES = {
    "ding": ["-f", "lavfi", "-i",
             "aevalsrc='(0.6*sin(2*PI*1319*t)+0.4*sin(2*PI*1976*t))*exp(-7*t)':d=0.7:s=44100"],
    "pop": ["-f", "lavfi", "-i",
            "aevalsrc='sin(2*PI*(420+260*exp(-30*t))*t)*exp(-22*t)':d=0.3:s=44100"],
    "whoosh": ["-f", "lavfi", "-i", "anoisesrc=d=0.6:c=pink:a=0.7:r=44100",
               "-af", "highpass=f=700,lowpass=f=7000,afade=t=in:d=0.25,afade=t=out:st=0.3:d=0.3,volume=3.5"],
}


def make_sfx(style: str, workdir: Path) -> Path:
    """Create a built-in effect sound with FFmpeg."""
    out = workdir / f"sfx_{style}.wav"
    run(["ffmpeg", "-y", *SFX_STYLES[style], "-ar", "44100", "-ac", "2", str(out)])
    return out


def mix_sfx(voice: Path, sfx: Path, starts: list[float], volume: float, workdir: Path) -> Path:
    """Overlay effect sounds on the narration at the requested start times."""
    count = len(starts)
    help_txt = subprocess.run(["ffmpeg", "-hide_banner", "-h", "filter=amix"],
                              capture_output=True, text=True).stdout
    has_norm = "normalize" in help_txt
    parts = [f"[1:a]aformat=sample_rates=44100:channel_layouts=stereo,volume={volume:.2f},"
             f"asplit={count}" + "".join(f"[s{i}]" for i in range(count))]
    for i, start in enumerate(starts):
        ms = max(int(start * 1000), 0)
        parts.append(f"[s{i}]adelay={ms}:all=1[d{i}]")
    labels = "".join(f"[d{i}]" for i in range(count))
    if has_norm:
        parts.append(f"[0:a]{labels}amix=inputs={count + 1}:duration=first:dropout_transition=0:normalize=0[out]")
    else:
        parts.append(f"[0:a]{labels}amix=inputs={count + 1}:duration=first:dropout_transition=0,"
                     f"volume={count + 1}[out]")
    out = workdir / "voice_sfx.wav"
    run(["ffmpeg", "-y", "-i", str(voice), "-i", str(sfx),
         "-filter_complex", ";".join(parts), "-map", "[out]", "-ar", "44100", "-ac", "2", str(out)])
    return out


def mix_bgm(mix: Path, bgm: Path, volume: float, duck: bool, workdir: Path) -> Path:
    """Mix looping background music under narration, optionally ducking its volume."""
    total = probe_duration(mix)
    help_txt = subprocess.run(["ffmpeg", "-hide_banner", "-h", "filter=amix"],
                              capture_output=True, text=True).stdout
    has_norm = "normalize" in help_txt
    fade_out_at = max(total - 2.0, 0)
    music = (f"[1:a]aformat=sample_rates=44100:channel_layouts=stereo,volume={volume:.2f},"
             f"afade=t=in:d=1.5,afade=t=out:st={fade_out_at:.2f}:d=2")
    if duck:
        parts = ["[0:a]asplit=2[v1][v2]",
                 music + "[b]",
                 "[b][v2]sidechaincompress=threshold=0.005:ratio=8:attack=15:release=600[bd]"]
        voice_label, music_label = "[v1]", "[bd]"
    else:
        parts = [music + "[b]"]
        voice_label, music_label = "[0:a]", "[b]"
    if has_norm:
        parts.append(f"{voice_label}{music_label}amix=inputs=2:duration=first:dropout_transition=0:normalize=0[out]")
    else:
        parts.append(f"{voice_label}{music_label}amix=inputs=2:duration=first:dropout_transition=0,volume=2[out]")
    out = workdir / "final_mix.wav"
    run(["ffmpeg", "-y", "-i", str(mix), "-stream_loop", "-1", "-i", str(bgm),
         "-filter_complex", ";".join(parts), "-map", "[out]", "-t", f"{total:.3f}",
         "-ar", "44100", "-ac", "2", str(out)])
    return out


def build_audio(clips: list[Path], durations: list[float], gap: float, lead: float,
                tail: float, workdir: Path, voice_delay: float = 0.0,
                pads: list[float] | None = None) -> tuple[Path, list[tuple[float, float]], float]:
    """Concatenate narration clips and return output path, cue times, and total duration."""
    wavs: list[Path] = []
    cues: list[tuple[float, float]] = []
    current_time = lead
    if lead > 0:
        silence = workdir / "silence_lead.wav"
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
             "-t", f"{lead}", str(silence)])
        wavs.append(silence)
    for i, (clip, duration) in enumerate(zip(clips, durations)):
        is_last = i == len(clips) - 1
        pad = pads[i] if pads else (tail if is_last else gap)
        segment = workdir / f"seg_{i}.wav"
        audio_filter = f"apad=pad_dur={pad}"
        if voice_delay > 0:
            audio_filter = f"adelay={int(voice_delay * 1000)}:all=1," + audio_filter
        run(["ffmpeg", "-y", "-i", str(clip), "-ar", "44100", "-ac", "2",
             "-af", audio_filter, "-t", f"{voice_delay + duration + pad}", str(segment)])
        wavs.append(segment)
        cues.append((current_time, current_time + voice_delay + duration + (tail if is_last else pad * 0.6)))
        current_time += voice_delay + duration + pad
    file_list = workdir / "audio_list.txt"
    file_list.write_text("".join(f"file '{path.as_posix()}'\n" for path in wavs), encoding="utf-8")
    out = workdir / "voice.wav"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(file_list), "-c", "copy", str(out)])
    return out, cues, current_time

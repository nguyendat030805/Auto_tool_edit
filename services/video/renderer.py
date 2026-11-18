"""FFmpeg video composition for the rendered comment cards."""
from __future__ import annotations

from pathlib import Path

from .media import run


def render(args, cards: list[Path], card_sizes, cues, audio: Path,
           total: float, out: Path) -> None:
    """Render the background, timed cards, and narration into an MP4."""
    width, height = args.size
    inputs = ["-stream_loop", "-1", "-i", str(args.bg)]
    for card in cards:
        inputs += ["-loop", "1", "-t", f"{total:.3f}", "-i", str(card)]
    inputs += ["-i", str(audio)]
    audio_idx = 1 + len(cards)

    bg = (f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
          f"crop={width}:{height},setsar=1,fps={args.fps}")
    if args.dim > 0:
        bg += f",eq=brightness={-args.dim:.2f}"
    bg += f",trim=duration={total:.3f},setpts=PTS-STARTPTS[bg0]"
    chains = [bg]

    last = "bg0"
    fade_in, fade_out = 0.30, 0.25
    has_post = args.post_image is not None
    for i, ((start, end), _) in enumerate(zip(cues, card_sizes)):
        index = i + 1
        is_post = has_post and i == 0
        zoom = ""
        if is_post:
            zoom = (f"scale=w='iw*(1+0.035*min(max((t-{start:.3f})/"
                    f"{max(end - start, 0.5):.3f},0),1))':h=-1:eval=frame,")
        chains.append(
            f"[{index}:v]format=rgba,{zoom}"
            f"fade=t=in:st={start:.3f}:d={fade_in}:alpha=1,"
            f"fade=t=out:st={end - fade_out:.3f}:d={fade_out}:alpha=1[c{i}]"
        )
        y_base = f"(H-h)/2+{0 if is_post else args.offset_y}"
        y = f"{y_base}+80*(1-min(max((t-{start:.3f})/{fade_in},0),1))"
        next_layer = f"v{i}"
        chains.append(f"[{last}][c{i}]overlay=x=(W-w)/2:y='{y}':eof_action=pass[{next_layer}]")
        last = next_layer

    command = ["ffmpeg", "-y", *inputs,
               "-filter_complex", ";".join(chains),
               "-map", f"[{last}]", "-map", f"{audio_idx}:a",
               "-t", f"{total:.3f}",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)]
    run(command)

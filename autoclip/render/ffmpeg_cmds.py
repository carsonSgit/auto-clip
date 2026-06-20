"""FFmpeg command builders. Pure string/list assembly — unit-testable without media."""

from pathlib import Path

# fmt: off
ENCODE_ARGS = [
    "-r", "30",
    "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
    "-c:a", "aac", "-b:a", "192k",
    "-movflags", "+faststart",
]
# fmt: on
LOUDNORM = "loudnorm=I=-16:TP=-1.5:LRA=11"


def build_render_command(
    source: Path,
    logo: Path,
    ass_path: Path,
    out_path: Path,
    clip_start: float,
    clip_end: float,
    layout: dict,
    canvas_bg_hex: str,
    fontsdir: Path,
) -> list[str]:
    duration = round(clip_end - clip_start, 3)
    W, H = layout["W"], layout["H"]
    # fmt: off
    base = [
        "ffmpeg", "-y", "-v", "error",
        "-ss", f"{clip_start:.3f}", "-t", f"{duration:.3f}", "-i", source.as_posix(),
        "-i", logo.as_posix(),
    ]
    # fmt: on
    # libass needs forward slashes in the filter graph even on Windows; as_posix()
    # also keeps the whole command host-deterministic (the runtime is Linux).
    subs = f"subtitles=filename={ass_path.as_posix()}:fontsdir={fontsdir.as_posix()}"

    if layout["kind"] == "landscape":  # landscape: video fills frame
        filters = (
            f"[0:v]scale={W}:{H}:force_original_aspect_ratio=decrease,"
            f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1[v0];"
            f"[1:v]scale={layout['logo_w']}:-1[logo];"
            f"[v0][logo]overlay={layout['logo_x']}:{layout['logo_y']}[v1];"
            f"[v1]{subs}[vout];"
            f"[0:a]{LOUDNORM}[aout]"
        )
        cmd = base
    else:  # canvas: branded background, centered video, top logo
        bg = f"color=c=0x{canvas_bg_hex.lstrip('#')}:s={W}x{H}:r=30:d={duration:.3f}"
        cmd = [*base, "-f", "lavfi", "-i", bg]
        filters = (
            f"[0:v]scale={layout['video_w']}:{layout['video_h']},setsar=1[vid];"
            f"[1:v]scale={layout['logo_w']}:-1[logo];"
            f"[2:v][vid]overlay={layout['video_x']}:{layout['video_y']}[b1];"
            f"[b1][logo]overlay={layout['logo_x']}:{layout['logo_y']}[b2];"
            f"[b2]{subs}[vout];"
            f"[0:a]{LOUDNORM}[aout]"
        )

    # fmt: off
    return [
        *cmd,
        "-filter_complex", filters,
        "-map", "[vout]", "-map", "[aout]",
        *ENCODE_ARGS,
        out_path.as_posix(),
    ]
    # fmt: on

"""ffprobe/ffmpeg helpers shared by pipeline stages."""

import json
import subprocess
from pathlib import Path


class MediaError(Exception):
    pass


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise MediaError(f"{cmd[0]} failed (exit {proc.returncode}): {proc.stderr[-2000:]}")
    return proc


def probe(path: Path) -> dict:
    proc = _run([
        "ffprobe", "-v", "error",
        "-print_format", "json",
        "-show_format", "-show_streams",
        str(path),
    ])
    return json.loads(proc.stdout)


def probe_video(path: Path) -> dict:
    """Probe and validate that the file contains a video + audio stream.

    Returns {"duration": float, "width": int, "height": int, "fps": float}.
    """
    info = probe(path)
    streams = info.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if video is None:
        raise MediaError("No video stream found — is this a video file?")
    if audio is None:
        raise MediaError("No audio stream found — cannot transcribe silent footage.")

    duration = float(info.get("format", {}).get("duration") or 0)
    if duration <= 0:
        raise MediaError("Could not determine media duration.")

    num, _, den = (video.get("avg_frame_rate") or "0/1").partition("/")
    fps = float(num) / float(den) if den and float(den) else 0.0

    return {
        "duration": duration,
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "fps": fps,
    }


def extract_audio(source: Path, dest_wav: Path) -> None:
    """Extract 16 kHz mono WAV for transcription."""
    dest_wav.parent.mkdir(parents=True, exist_ok=True)
    _run([
        "ffmpeg", "-y", "-v", "error",
        "-i", str(source),
        "-vn", "-ac", "1", "-ar", "16000",
        str(dest_wav),
    ])

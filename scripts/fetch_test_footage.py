"""Download golden test footage (public conference talks) into /samples.

Run inside the container so yt-dlp/ffmpeg are available:

    docker compose run --rm web python scripts/fetch_test_footage.py
    docker compose run --rm web python scripts/fetch_test_footage.py --url <video-url>

Files land in ./data/samples on the host (bind mount) — upload them through
the web UI at http://localhost:8000.
"""

import argparse
from pathlib import Path

import yt_dlp

DEFAULT_QUERIES = [
    # Stable searches rather than hardcoded video IDs; capped to 10-30 min talks.
    "ytsearch1:conference talk software engineering keynote",
    "ytsearch1:tech conference panel discussion",
]

OUT_DIR = Path("/samples")


def fetch(target: str) -> None:
    opts = {
        "format": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]",
        "merge_output_format": "mp4",
        "outtmpl": str(OUT_DIR / "%(title).80s.%(ext)s"),
        "match_filter": yt_dlp.utils.match_filter_func("duration > 540 & duration < 1900"),
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([target])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", help="Specific video URL instead of the default searches")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    targets = [args.url] if args.url else DEFAULT_QUERIES
    for target in targets:
        try:
            fetch(target)
        except Exception as exc:  # keep going; golden assets are best-effort
            print(f"WARN: failed to fetch {target}: {exc}")

    print("Done. Files in ./data/samples:")
    for p in sorted(OUT_DIR.glob("*")):
        print(f"  {p.name}")

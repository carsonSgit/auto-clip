import os
import tempfile
from pathlib import Path

import pytest

# Must run before any autoclip import: settings is built at import time.
_TMP = Path(tempfile.mkdtemp(prefix="autoclip-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["DATA_DIR"] = str(_TMP / "data")
os.environ["OUTPUT_DIR"] = str(_TMP / "outputs")


@pytest.fixture
def transcript():
    """Synthetic 120s talk: continuous speech 0-50s, silence 50-70s, speech 70-120s."""
    segments = []
    sid = 0
    for start in range(0, 50, 5):
        segments.append(
            {
                "id": sid,
                "start": float(start),
                "end": float(start + 5),
                "text": f"Sentence number {sid} about our product.",
                "speaker": None,
                "words": [],
            }
        )
        sid += 1
    for start in range(70, 120, 5):
        segments.append(
            {
                "id": sid,
                "start": float(start),
                "end": float(start + 5),
                "text": f"Closing point {sid} for the audience.",
                "speaker": None,
                "words": [],
            }
        )
        sid += 1
    return {"language": "en", "duration": 120.0, "model": "test", "segments": segments}


@pytest.fixture
def brand():
    return {
        "name": "Test Brand",
        "colors": {"canvas_bg": "#0F1B2D", "accent": "#3BA7F0", "text": "#FFFFFF"},
        "font": {"family": "DejaVu Sans", "files": []},
        "logo": {
            "light": "/x/logo_white.png",
            "dark": "/x/logo.png",
            "corner": "top-right",
            "margin_px": 48,
            "width_frac": 0.22,
        },
        "subtitles": {
            "font_size": 64,
            "text_color": "#FFFFFF",
            "outline_color": "#000000",
            "outline_px": 3,
            "highlight_color": "#3BA7F0",
        },
        "headline": {"enabled": True, "template": "{title}", "font_size": 72},
        "voice": "test voice",
    }

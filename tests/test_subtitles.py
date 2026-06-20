from autoclip.render.subtitles import _ass_color, _ass_time, build_ass


def test_ass_color_is_bgr():
    assert _ass_color("#3BA7F0") == "&H00F0A73B"


def test_ass_time_format():
    assert _ass_time(0) == "0:00:00.00"
    assert _ass_time(75.5) == "0:01:15.50"
    assert _ass_time(3661.25) == "1:01:01.25"


def test_build_ass_shifts_and_clips_segments(tmp_path, transcript, brand):
    layout = {"W": 1080, "H": 1920, "sub_margin_v": 280, "headline": True, "headline_margin_v": 160}
    dest = tmp_path / "subs.ass"
    build_ass(
        transcript,
        clip_start=10.0,
        clip_end=30.0,
        layout=layout,
        brand=brand,
        headline_text="Big Moment",
        dest=dest,
    )
    content = dest.read_text(encoding="utf-8")

    assert "PlayResX: 1080" in content
    assert "Big Moment" in content
    dialogue_lines = [
        line for line in content.splitlines() if line.startswith("Dialogue:") and ",Sub," in line
    ]
    # Segments 10-15, 15-20, 20-25, 25-30 fall in range -> 4 caption events
    assert len(dialogue_lines) == 4
    assert dialogue_lines[0].split(",")[1] == "0:00:00.00"  # shifted to clip-relative time
    # Nothing outside the clip window
    assert "Sentence number 0 " not in content


def test_build_ass_escapes_override_braces(tmp_path, brand):
    transcript = {
        "segments": [
            {"id": 0, "start": 0.0, "end": 5.0, "text": "curly {\\b1} attack", "speaker": None, "words": []},
        ]
    }
    layout = {"W": 1920, "H": 1080, "sub_margin_v": 60, "headline": False, "headline_margin_v": 0}
    dest = tmp_path / "subs.ass"
    build_ass(transcript, 0.0, 5.0, layout, brand, headline_text="", dest=dest)
    assert "{" not in dest.read_text(encoding="utf-8").split("[Events]")[1]

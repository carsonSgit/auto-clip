import pytest

from autoclip.llm.anthropic_provider import _extract_json, _sanitize_highlights

# ---------------------------------------------------------------------------
# _extract_json
# ---------------------------------------------------------------------------


def test_extract_json_plain_array():
    result = _extract_json("[1, 2, 3]")
    assert result == [1, 2, 3]


def test_extract_json_fenced_block():
    result = _extract_json("```json\n[1, 2]\n```")
    assert result == [1, 2]


def test_extract_json_prose_before():
    result = _extract_json('Here you go: {"a": 1}')
    assert result == {"a": 1}


def test_extract_json_no_json_raises():
    with pytest.raises(ValueError, match="no JSON found"):
        _extract_json("sorry, I cannot help with that")


# ---------------------------------------------------------------------------
# _sanitize_highlights  (reuses the `transcript` fixture from conftest)
# ---------------------------------------------------------------------------


def _item(start, end, title="Test Clip", rationale="A good reason"):
    return {"start": start, "end": end, "title": title, "rationale": rationale}


def test_sanitize_valid_item_survives(transcript):
    data = [_item(0.0, 25.0)]
    result = _sanitize_highlights(data, transcript, clip_count=3, min_seconds=10, max_seconds=30)
    assert len(result) == 1
    item = result[0]
    # start must be snapped to a segment start (multiples of 5 in the fixture)
    assert item["start"] % 5 == 0.0
    # end must be snapped to a segment end (5, 10, ..., 50, 75, 80, ...)
    assert item["end"] % 5 == 0.0


def test_sanitize_clamps_end_beyond_duration(transcript):
    # 70 -> 500: end clamps to 120.0, snapped start=70.0, snapped end=120.0 → span=50s.
    # With max_seconds=60, 50s ≤ 60*1.5=90 → survives.
    data = [_item(70.0, 500.0)]
    result = _sanitize_highlights(data, transcript, clip_count=3, min_seconds=10, max_seconds=60)
    assert len(result) == 1
    # end must be <= duration (120s)
    assert result[0]["end"] <= 120.0


def test_sanitize_drops_too_short(transcript):
    # The only way an item is too short after snapping is if the snapped span < min_seconds * 0.5.
    # Use min_seconds=20 so threshold is 10s. Segments are 5s wide, so snapped span is at least 5s.
    # An item from 52 -> 68 falls entirely in the gap (50-70); start snaps to 50.0, end snaps to 70.0
    # → span = 20s which is not < 10. Instead, use min_seconds=30 → threshold=15s and provide
    # two items that after snapping are each 5s wide (one segment apart).
    # start=0, end=3 → snaps to 0→5 = 5s; threshold = 30*0.5=15s → 5 < 15 → dropped.
    data = [_item(0.0, 3.0)]
    with pytest.raises(ValueError):
        _sanitize_highlights(data, transcript, clip_count=3, min_seconds=30, max_seconds=90)


def test_sanitize_drops_overlapping(transcript):
    # Two overlapping items — only the earlier-starting one should survive
    data = [
        _item(0.0, 25.0, title="First"),
        _item(10.0, 35.0, title="Second"),
    ]
    result = _sanitize_highlights(data, transcript, clip_count=3, min_seconds=10, max_seconds=30)
    assert len(result) == 1
    assert result[0]["title"] == "First"


def test_sanitize_all_unusable_raises(transcript):
    # Items that are too short even after snapping: use min_seconds=30 (threshold=15s).
    # 0→3 snaps to 0→5 = 5s < 15s → dropped; 5→8 snaps to 5→10 = 5s < 15s → dropped.
    data = [_item(0.0, 3.0), _item(5.0, 8.0)]
    with pytest.raises(ValueError):
        _sanitize_highlights(data, transcript, clip_count=3, min_seconds=30, max_seconds=90)


def test_sanitize_truncates_to_clip_count(transcript):
    # Provide 5 valid non-overlapping items; clip_count=3 → only 3 returned
    data = [_item(0.0, 15.0, title=f"Clip {i}") for i in range(5)]
    # Make them non-overlapping: spread them across the transcript
    data = [_item(float(i * 20), float(i * 20 + 15), title=f"Clip {i}") for i in range(5)]
    # Only first 4 will land in segment-covered regions (0-50 and 70-120)
    # Use segments we know exist: 0-15, 20-35, 70-85, 90-105
    data = [
        _item(0.0, 15.0, title="Clip 0"),
        _item(20.0, 35.0, title="Clip 1"),
        _item(70.0, 85.0, title="Clip 2"),
        _item(90.0, 105.0, title="Clip 3"),
    ]
    result = _sanitize_highlights(data, transcript, clip_count=3, min_seconds=10, max_seconds=30)
    assert len(result) == 3

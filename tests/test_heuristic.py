from autoclip.llm.heuristic import select_highlights


def test_returns_requested_count_within_bounds(transcript):
    highlights = select_highlights(transcript, [25.0, 70.0], clip_count=3, min_seconds=10, max_seconds=30)
    assert 1 <= len(highlights) <= 3
    for h in highlights:
        assert 10 <= h["end"] - h["start"] <= 30
        assert h["title"]


def test_no_overlaps(transcript):
    highlights = select_highlights(transcript, [], clip_count=5, min_seconds=10, max_seconds=40)
    ordered = sorted(highlights, key=lambda h: h["start"])
    for a, b in zip(ordered, ordered[1:]):
        assert a["end"] <= b["start"]


def test_empty_transcript():
    assert select_highlights({"segments": []}, [], 3, 10, 30) == []


def test_respects_silence_gap(transcript):
    # No window may straddle the 50-70s silence and exceed max length.
    highlights = select_highlights(transcript, [], clip_count=4, min_seconds=10, max_seconds=25)
    for h in highlights:
        assert not (h["start"] < 50 < h["end"] and h["end"] - h["start"] > 25)

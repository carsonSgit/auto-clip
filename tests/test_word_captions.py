from autoclip.render.subtitles import build_ass

LAYOUT = {"W": 1080, "H": 1920, "sub_margin_v": 280, "headline": False, "headline_margin_v": 0}


def _worded_transcript():
    words = []
    t = 10.0
    for token in ["the", "quick", "brown", "fox", "jumps", "over", "the", "lazy", "dog"]:
        words.append({"word": token, "start": round(t, 2), "end": round(t + 0.4, 2)})
        t += 0.5
    return {
        "segments": [
            {
                "id": 0,
                "start": 10.0,
                "end": t,
                "text": "the quick brown fox jumps over the lazy dog",
                "speaker": None,
                "words": words,
            }
        ]
    }


def test_word_mode_emits_one_event_per_word(tmp_path, brand):
    brand["subtitles"]["mode"] = "word"
    dest = tmp_path / "w.ass"
    build_ass(_worded_transcript(), 10.0, 20.0, LAYOUT, brand, headline_text="", dest=dest)
    events = [line for line in dest.read_text(encoding="utf-8").splitlines() if line.startswith("Dialogue:")]
    assert len(events) == 9  # one per word
    # Active-word highlight uses the accent color (#3BA7F0 -> &H00F0A73B) and bold
    assert all("\\b1\\c&H00F0A73B&" in e for e in events)
    # Groups respect the char budget: no event shows the whole 9-word sentence
    assert not any("lazy" in e and "quick" in e for e in events)


def test_word_mode_falls_back_to_segment_without_words(tmp_path, brand, transcript):
    brand["subtitles"]["mode"] = "word"  # fixture transcript has empty word lists
    dest = tmp_path / "f.ass"
    build_ass(transcript, 10.0, 30.0, LAYOUT, brand, headline_text="", dest=dest)
    events = [line for line in dest.read_text(encoding="utf-8").splitlines() if line.startswith("Dialogue:")]
    assert len(events) == 4  # one per segment in range, as in segment mode


def test_segment_mode_still_available(tmp_path, brand):
    brand["subtitles"]["mode"] = "segment"
    dest = tmp_path / "s.ass"
    build_ass(_worded_transcript(), 10.0, 20.0, LAYOUT, brand, headline_text="", dest=dest)
    events = [line for line in dest.read_text(encoding="utf-8").splitlines() if line.startswith("Dialogue:")]
    assert len(events) == 1
    assert "quick brown fox" in events[0]

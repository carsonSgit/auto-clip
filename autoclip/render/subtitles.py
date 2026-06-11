"""Brand-styled ASS subtitle generation.

Two caption modes, selected by brand.yaml subtitles.mode:
- "word" (default): social-style animated captions — short word groups with the
  currently spoken word highlighted in the brand accent color, one ASS event
  per word. Falls back to segment mode for segments without word timestamps.
- "segment": classic phrase subtitles, one event per transcript segment.

The clip headline is a top-anchored ASS event on canvas layouts — keeping all
text in libass avoids ffmpeg drawtext escaping entirely.
"""

from pathlib import Path

MAX_GROUP_CHARS = 26  # chars per caption group in word mode (~2 short lines max)


def _ass_color(hex_rgb: str) -> str:
    """#RRGGBB -> ASS &H00BBGGRR."""
    value = hex_rgb.lstrip("#")
    r, g, b = value[0:2], value[2:4], value[4:6]
    return f"&H00{b}{g}{r}".upper()


def _ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int(seconds % 3600 // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _escape(text: str) -> str:
    return text.replace("{", "(").replace("}", ")").replace("\n", r"\N")


def build_ass(
    transcript: dict,
    clip_start: float,
    clip_end: float,
    layout: dict,
    brand: dict,
    headline_text: str,
    dest: Path,
) -> Path:
    subs = brand["subtitles"]
    font = brand["font"]["family"]
    primary = _ass_color(subs.get("text_color", "#FFFFFF"))
    outline_color = _ass_color(subs.get("outline_color", "#000000"))
    accent = _ass_color(brand["colors"].get("accent", "#3BA7F0"))
    font_size = int(subs.get("font_size", 64))
    outline = int(subs.get("outline_px", 3))
    headline_size = int(brand.get("headline", {}).get("font_size", 72))

    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {layout['W']}",
        f"PlayResY: {layout['H']}",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Sub,{font},{font_size},{primary},{accent},{outline_color},&H64000000,"
        f"-1,0,0,0,100,100,0,0,1,{outline},0,2,60,60,{layout['sub_margin_v']},1",
        f"Style: Headline,{font},{headline_size},{primary},{accent},{outline_color},&H64000000,"
        f"-1,0,0,0,100,100,0,0,1,0,0,8,40,40,{layout['headline_margin_v']},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    duration = clip_end - clip_start
    if layout.get("headline") and headline_text:
        lines.append(
            f"Dialogue: 0,{_ass_time(0)},{_ass_time(duration)},Headline,,0,0,0,,{_escape(headline_text)}"
        )

    mode = brand["subtitles"].get("mode", "word")
    for seg in transcript["segments"]:
        if seg["end"] <= clip_start or seg["start"] >= clip_end:
            continue
        if mode == "word" and seg.get("words"):
            lines.extend(_word_events(seg, clip_start, clip_end, accent))
        else:
            lines.extend(_segment_event(seg, clip_start, clip_end))

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dest


def _segment_event(seg: dict, clip_start: float, clip_end: float) -> list[str]:
    start = max(seg["start"], clip_start) - clip_start
    end = min(seg["end"], clip_end) - clip_start
    if end - start < 0.1 or not seg["text"]:
        return []
    return [f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Sub,,0,0,0,,{_escape(seg['text'])}"]


def _word_events(seg: dict, clip_start: float, clip_end: float, accent: str) -> list[str]:
    """One event per spoken word: its group stays on screen, the active word
    is highlighted in the accent color and bolded."""
    words = [w for w in seg["words"] if w["end"] > clip_start and w["start"] < clip_end and w["word"]]
    if not words:
        return _segment_event(seg, clip_start, clip_end)

    groups: list[list[dict]] = [[]]
    chars = 0
    for w in words:
        if groups[-1] and chars + len(w["word"]) + 1 > MAX_GROUP_CHARS:
            groups.append([])
            chars = 0
        groups[-1].append(w)
        chars += len(w["word"]) + 1

    events = []
    for group in groups:
        group_end = min(group[-1]["end"], clip_end) - clip_start
        for k, w in enumerate(group):
            start = max(w["start"], clip_start) - clip_start
            # Hold each frame until the next word starts so the group never flickers.
            end = (max(group[k + 1]["start"], clip_start) - clip_start) if k + 1 < len(group) else group_end
            if end - start < 0.02:
                continue
            text = " ".join(
                f"{{\\b1\\c{accent}&}}{_escape(x['word'])}{{\\b0\\c}}" if j == k else _escape(x["word"])
                for j, x in enumerate(group)
            )
            events.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Sub,,0,0,0,,{text}")
    return events

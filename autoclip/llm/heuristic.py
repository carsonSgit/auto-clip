"""Offline highlight selection: no LLM, pure transcript + scene heuristics.

Scores candidate windows by speech density, length, and proximity of the end
to a scene boundary, then greedily picks non-overlapping top scorers.
"""


def select_highlights(
    transcript: dict,
    scene_boundaries: list[float],
    clip_count: int,
    min_seconds: float,
    max_seconds: float,
) -> list[dict]:
    segments = [s for s in transcript.get("segments", []) if s["end"] > s["start"]]
    if not segments:
        return []

    windows = []
    for i in range(len(segments)):
        start = segments[i]["start"]
        speech = 0.0
        for j in range(i, len(segments)):
            seg = segments[j]
            if seg["end"] - start > max_seconds:
                break
            speech += seg["end"] - seg["start"]
            end = seg["end"]
            length = end - start
            if length < min_seconds:
                continue
            density = speech / length
            scene_snap = min((abs(end - b) for b in scene_boundaries), default=1e9)
            score = density + (0.15 if scene_snap < 1.0 else 0.0) + 0.1 * min(length / max_seconds, 1.0)
            windows.append({"start": start, "end": end, "score": score, "seg_range": (i, j)})

    windows.sort(key=lambda w: -w["score"])
    chosen: list[dict] = []
    for w in windows:
        if all(w["end"] <= c["start"] or w["start"] >= c["end"] for c in chosen):
            chosen.append(w)
        if len(chosen) >= clip_count:
            break
    chosen.sort(key=lambda w: w["start"])

    highlights = []
    for w in chosen:
        i, j = w["seg_range"]
        text = " ".join(s["text"] for s in segments[i : j + 1])
        highlights.append(
            {
                "start": round(w["start"], 3),
                "end": round(w["end"], 3),
                "title": _title_from_text(text),
                "rationale": "Heuristic pick: dense, well-bounded speech segment.",
            }
        )
    return highlights


def _title_from_text(text: str, max_words: int = 8) -> str:
    words = text.split()
    title = " ".join(words[:max_words]).strip(" ,.;:!?-")
    return title + ("…" if len(words) > max_words else "")

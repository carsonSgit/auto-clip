"""LLM highlight selection + post copy via the Anthropic API.

Both entry points raise on failure after one retry; callers fall back to the
heuristic/excerpt implementations so the pipeline never requires an API key.
"""

import json

import jsonschema

from autoclip.config import settings

HIGHLIGHTS_SCHEMA = {
    "type": "array",
    "minItems": 1,
    "items": {
        "type": "object",
        "required": ["start", "end", "title", "rationale"],
        "properties": {
            "start": {"type": "number", "minimum": 0},
            "end": {"type": "number", "minimum": 0},
            "title": {"type": "string", "maxLength": 200},
            "rationale": {"type": "string"},
        },
    },
}

POST_COPY_SCHEMA = {
    "type": "object",
    "patternProperties": {
        ".*": {  # clip index as string key
            "type": "object",
            "required": ["linkedin", "instagram", "tiktok", "youtube"],
            "properties": {p: {"type": "string"} for p in ("linkedin", "instagram", "tiktok", "youtube")},
        }
    },
}


def _client():
    import anthropic

    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _complete_json(system: str, user: str, schema: dict):
    """One call + one schema-feedback retry; raises on second failure."""
    client = _client()
    messages = [{"role": "user", "content": user}]
    for attempt in range(2):
        response = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=4096,
            system=system,
            messages=messages,
        )
        text = "".join(block.text for block in response.content if block.type == "text")
        try:
            data = _extract_json(text)
            jsonschema.validate(data, schema)
            return data
        except (ValueError, jsonschema.ValidationError) as exc:
            if attempt == 1:
                raise
            messages.append({"role": "assistant", "content": text})
            messages.append({
                "role": "user",
                "content": f"Your response failed validation: {exc}. "
                           "Reply with ONLY the corrected JSON, no other text.",
            })


def _extract_json(text: str):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1].lstrip("json").strip()
    start = min((i for i in (text.find("["), text.find("{")) if i >= 0), default=-1)
    if start < 0:
        raise ValueError("no JSON found in response")
    return json.loads(text[start:])


def select_highlights(
    transcript: dict,
    scene_boundaries: list[float],
    context_text: str,
    brand_voice: str,
    clip_count: int,
    min_seconds: float,
    max_seconds: float,
) -> list[dict]:
    duration = transcript.get("duration", 0)
    segment_lines = "\n".join(
        f"[{s['start']:.1f}-{s['end']:.1f}] {s['text']}" for s in transcript["segments"]
    )
    system = (
        "You select highlight clips from event-footage transcripts for social media. "
        "Pick self-contained moments: a complete point, story, or quote that works without "
        "surrounding context. Prefer hooks that grab attention in the first seconds. "
        "Clip boundaries MUST land on the segment timestamps given (start of one segment, "
        "end of the same or a later segment). Respond with ONLY a JSON array, no prose."
    )
    user = f"""Event context: {context_text or "(none provided)"}
Brand voice notes: {brand_voice}
Video duration: {duration:.0f}s
Scene-change timestamps (s): {", ".join(f"{b:.1f}" for b in scene_boundaries) or "(none)"}

Select exactly {clip_count} non-overlapping clips, each {min_seconds:.0f}-{max_seconds:.0f} seconds long.
Return a JSON array of {{"start": <s>, "end": <s>, "title": "<short punchy title>", "rationale": "<why>"}}.

Transcript segments:
{segment_lines}"""

    data = _complete_json(system, user, HIGHLIGHTS_SCHEMA)
    return _sanitize_highlights(data, transcript, clip_count, min_seconds, max_seconds)


def _sanitize_highlights(
    data: list[dict], transcript: dict, clip_count: int, min_seconds: float, max_seconds: float
) -> list[dict]:
    """Clamp to media duration, snap to segment boundaries, drop invalid/overlapping."""
    duration = transcript.get("duration", 0) or max(
        (s["end"] for s in transcript["segments"]), default=0
    )
    starts = sorted(s["start"] for s in transcript["segments"])
    ends = sorted(s["end"] for s in transcript["segments"])

    def snap(value: float, candidates: list[float]) -> float:
        return min(candidates, key=lambda c: abs(c - value)) if candidates else value

    cleaned = []
    for item in sorted(data, key=lambda d: d["start"]):
        start = snap(max(0.0, min(item["start"], duration)), starts)
        end = snap(max(0.0, min(item["end"], duration)), ends)
        if end - start < min_seconds * 0.5 or end - start > max_seconds * 1.5:
            continue
        if any(start < c["end"] and end > c["start"] for c in cleaned):
            continue
        cleaned.append({
            "start": round(start, 3),
            "end": round(end, 3),
            "title": item["title"].strip()[:200],
            "rationale": item["rationale"].strip(),
        })
    if not cleaned:
        raise ValueError("LLM returned no usable highlight ranges")
    return cleaned[:clip_count]


def generate_post_copy(clips: list[dict], context_text: str, brand_voice: str) -> dict:
    """Returns {clip_index_str: {platform: copy}} for linkedin/instagram/tiktok/youtube."""
    clip_lines = "\n\n".join(
        f"Clip {i}: \"{c['title']}\"\nTranscript excerpt: {c['excerpt']}" for i, c in enumerate(clips)
    )
    system = (
        "You write social media post copy for event highlight clips. "
        "Follow the brand voice exactly. Tailor tone and length per platform: "
        "linkedin = professional, 2-4 short paragraphs; instagram = casual + hashtags; "
        "tiktok = short, punchy, hashtags; youtube = title-style first line + 1-2 sentences. "
        "Respond with ONLY a JSON object, no prose."
    )
    user = f"""Event context: {context_text or "(none provided)"}
Brand voice: {brand_voice}

Write post copy for each clip below. Return JSON:
{{"0": {{"linkedin": "...", "instagram": "...", "tiktok": "...", "youtube": "..."}}, "1": {{...}}, ...}}

{clip_lines}"""
    return _complete_json(system, user, POST_COPY_SCHEMA)

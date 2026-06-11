"""Highlight selection + post copy dispatch: LLM when a key is configured,
heuristic/excerpt fallback otherwise or on LLM failure."""

import logging

from autoclip.config import settings
from autoclip.llm import anthropic_provider, heuristic

logger = logging.getLogger(__name__)

PLATFORMS = ("linkedin", "instagram", "tiktok", "youtube")


def select_highlights(
    transcript: dict,
    scene_boundaries: list[float],
    context_text: str,
    brand_voice: str,
    clip_count: int,
    min_seconds: float,
    max_seconds: float,
) -> tuple[list[dict], str]:
    """Returns (highlights, selector_used)."""
    if settings.anthropic_api_key:
        try:
            highlights = anthropic_provider.select_highlights(
                transcript, scene_boundaries, context_text, brand_voice,
                clip_count, min_seconds, max_seconds,
            )
            return highlights, "llm"
        except Exception:
            logger.exception("LLM highlight selection failed; falling back to heuristic")

    highlights = heuristic.select_highlights(
        transcript, scene_boundaries, clip_count, min_seconds, max_seconds,
    )
    return highlights, "heuristic"


def generate_post_copy(clips: list[dict], context_text: str, brand_voice: str) -> dict:
    """clips: [{"title": str, "excerpt": str}]. Returns {clip_index_str: {platform: copy}}."""
    if settings.anthropic_api_key:
        try:
            return anthropic_provider.generate_post_copy(clips, context_text, brand_voice)
        except Exception:
            logger.exception("LLM post copy failed; falling back to excerpts")

    return {
        str(i): {platform: f"{c['title']}\n\n“{c['excerpt']}”" for platform in PLATFORMS}
        for i, c in enumerate(clips)
    }

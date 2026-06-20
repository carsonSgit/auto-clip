"""Tests for compute_layout geometry — covers portrait/square sources and kind field."""

from pathlib import Path

from autoclip.render.ffmpeg_cmds import build_render_command
from autoclip.render.formats import FORMATS
from autoclip.render.layout import compute_layout


def test_portrait_source_on_1x1_fits_frame(brand):
    """Portrait 1080x1920 source on 1080x1080 canvas: video stays within bounds."""
    layout = compute_layout(FORMATS["1x1"], 1080, 1920, 720, 200, brand)
    assert layout["video_h"] <= 1080
    assert layout["video_y"] >= 0
    assert layout["video_x"] > 0
    assert layout["video_x"] + layout["video_w"] <= 1080
    assert layout["video_w"] % 2 == 0


def test_portrait_source_on_9x16_fills_frame(brand):
    """Portrait 1080x1920 source on 1080x1920 canvas: video fills the frame exactly."""
    layout = compute_layout(FORMATS["9x16"], 1080, 1920, 720, 200, brand)
    assert layout["video_w"] == 1080
    assert layout["video_h"] == 1920
    assert layout["video_x"] == 0
    assert layout["video_y"] == 0


def test_square_source_on_1x1_uses_canvas_branch(brand):
    """Square 1080x1080 source on 1x1: must route to canvas branch (branded bg), not landscape."""
    layout = compute_layout(FORMATS["1x1"], 1080, 1080, 720, 200, brand)
    cmd = build_render_command(
        Path("/data/src.mp4"),
        Path("/x/logo_white.png"),
        Path("/w/c0.ass"),
        Path("/outputs/j/clip_0/1x1.mp4"),
        clip_start=0.0,
        clip_end=30.0,
        layout=layout,
        canvas_bg_hex="#0F1B2D",
        fontsdir=Path("/app/brandkit/assets/fonts"),
    )
    assert "color=" in " ".join(cmd)


def test_landscape_source_on_canvas_unchanged(brand):
    """Landscape 1920x1080 source on 9x16 canvas: mainline path produces expected geometry."""
    layout = compute_layout(FORMATS["9x16"], 1920, 1080, 720, 200, brand)
    assert layout["video_w"] == 1080
    assert layout["video_h"] == 608
    assert layout["video_x"] == 0


def test_kind_field_on_all_formats(brand):
    """16x9 layout has kind='landscape'; other three have kind='canvas'."""
    landscape_layout = compute_layout(FORMATS["16x9"], 1920, 1080, 720, 200, brand)
    assert landscape_layout["kind"] == "landscape"

    for fmt_name in ("9x16", "1x1", "4x5"):
        layout = compute_layout(FORMATS[fmt_name], 1920, 1080, 720, 200, brand)
        assert layout["kind"] == "canvas", f"{fmt_name} should be canvas, got {layout['kind']}"

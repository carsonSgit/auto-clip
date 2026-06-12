from pathlib import Path

from autoclip.render.ffmpeg_cmds import build_render_command
from autoclip.render.formats import FORMATS
from autoclip.render.layout import compute_layout


def _cmd(brand, fmt_name):
    layout = compute_layout(FORMATS[fmt_name], 1920, 1080, 720, 200, brand)
    return build_render_command(
        Path("/data/src.mp4"), Path("/x/logo_white.png"), Path("/w/c0.ass"),
        Path("/outputs/j/clip_0") / f"{fmt_name}.mp4",
        clip_start=12.5, clip_end=42.5, layout=layout,
        canvas_bg_hex="#0F1B2D", fontsdir=Path("/app/brandkit/assets/fonts"),
    ), layout


def test_landscape_command(brand):
    cmd, _ = _cmd(brand, "16x9")
    joined = " ".join(cmd)
    assert "-ss 12.500 -t 30.000" in joined
    assert "color=" not in joined  # no canvas background
    assert "subtitles=filename=/w/c0.ass" in joined
    assert "loudnorm" in joined
    assert cmd[-1] == "/outputs/j/clip_0/16x9.mp4"


def test_canvas_command_has_branded_background(brand):
    cmd, layout = _cmd(brand, "9x16")
    joined = " ".join(cmd)
    assert "color=c=0x0F1B2D:s=1080x1920" in joined
    assert f"overlay={layout['video_x']}:{layout['video_y']}" in joined
    assert "[2:v]" in joined  # lavfi background is the third input


def test_canvas_layout_geometry(brand):
    layout = compute_layout(FORMATS["9x16"], 1920, 1080, 720, 200, brand)
    assert layout["video_w"] == 1080
    assert layout["video_h"] == 608  # 1080 * 1080/1920 rounded to even
    assert 0 < layout["video_y"] < 1920 - layout["video_h"]
    assert layout["headline"] is True
    assert layout["sub_margin_v"] >= 40


def test_all_formats_produce_commands(brand):
    for fmt_name in FORMATS:
        cmd, _ = _cmd(brand, fmt_name)
        assert cmd[0] == "ffmpeg"
        assert "-filter_complex" in cmd

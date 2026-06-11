"""Per-clip rendering across all platform formats."""

import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from autoclip import media
from autoclip.config import settings
from autoclip.render.ffmpeg_cmds import build_render_command
from autoclip.render.formats import FORMATS
from autoclip.render.layout import compute_layout
from autoclip.render.subtitles import build_ass

logger = logging.getLogger(__name__)


def render_clip(
    source: Path,
    src_info: dict,
    clip: dict,  # {"index", "start", "end", "title"}
    transcript: dict,
    brand: dict,
    brandkit_dir: Path,
    work_dir: Path,
    out_dir: Path,
) -> dict[str, Path]:
    """Render one highlight into every format. Returns {format_name: output_path}."""
    logo_light = Path(brand["logo"]["light"])
    logo_info = media.probe(logo_light)
    logo_stream = next(s for s in logo_info["streams"] if s.get("codec_type") == "video")
    logo_w, logo_h = int(logo_stream["width"]), int(logo_stream["height"])
    fontsdir = brandkit_dir / "assets" / "fonts"

    clip_dir = out_dir / f"clip_{clip['index']}"
    clip_dir.mkdir(parents=True, exist_ok=True)

    def _render_format(fmt_name: str) -> tuple[str, Path]:
        fmt = FORMATS[fmt_name]
        layout = compute_layout(fmt, src_info["width"], src_info["height"], logo_w, logo_h, brand)
        ass_path = work_dir / f"clip_{clip['index']}_{fmt_name}.ass"
        build_ass(
            transcript, clip["start"], clip["end"], layout, brand,
            headline_text=clip["title"], dest=ass_path,
        )
        out_path = clip_dir / f"{fmt_name}.mp4"
        cmd = build_render_command(
            source, logo_light, ass_path, out_path,
            clip["start"], clip["end"], layout,
            canvas_bg_hex=brand["colors"]["canvas_bg"],
            fontsdir=fontsdir,
        )
        logger.info("Rendering clip %s %s", clip["index"], fmt_name)
        media._run(cmd)
        return fmt_name, out_path

    workers = max(1, settings.render_parallelism)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        outputs = dict(pool.map(_render_format, FORMATS))

    return outputs

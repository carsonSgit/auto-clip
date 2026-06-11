"""Pixel layout for each output format, derived from brand kit + source/logo geometry."""


def _even(value: float) -> int:
    return int(round(value / 2) * 2)


def compute_layout(
    fmt: dict,
    source_w: int,
    source_h: int,
    logo_w: int,
    logo_h: int,
    brand: dict,
) -> dict:
    W, H = fmt["width"], fmt["height"]
    margin = int(brand["logo"].get("margin_px", 48))
    logo_frac = float(brand["logo"].get("width_frac", 0.22))

    if fmt["layout"] == "landscape":
        bug_w = _even(W * logo_frac * 0.6)
        return {
            "W": W, "H": H,
            "video_w": W, "video_h": H, "video_y": 0,
            "logo_w": bug_w,
            "logo_x": f"{W}-w-{margin}",  # ffmpeg overlay expression (top-right)
            "logo_y": str(margin),
            "sub_margin_v": 60,
            "headline": False,
            "headline_margin_v": 0,
        }

    # Canvas: full-width video, vertically biased slightly above center.
    video_w = W
    video_h = _even(video_w * source_h / source_w)
    video_y = int((H - video_h) * 0.45)
    scaled_logo_w = _even(W * logo_frac)
    scaled_logo_h = int(scaled_logo_w * logo_h / max(logo_w, 1))
    bottom_band = H - (video_y + video_h)
    return {
        "W": W, "H": H,
        "video_w": video_w, "video_h": video_h, "video_y": video_y,
        "logo_w": scaled_logo_w,
        "logo_x": f"({W}-w)/2",
        "logo_y": str(margin),
        "sub_margin_v": max(40, int(bottom_band * 0.4)),
        "headline": bool(brand.get("headline", {}).get("enabled", True)),
        "headline_margin_v": margin + scaled_logo_h + 36,
    }

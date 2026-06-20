"""Platform output formats. layout: "landscape" = full-frame video with corner
logo bug; "canvas" = video letterboxed on a branded background with logo +
headline above and captions below."""

FORMATS = {
    "16x9": {
        "width": 1920,
        "height": 1080,
        "layout": "landscape",
        "platforms": ["LinkedIn", "YouTube"],
    },
    "9x16": {
        "width": 1080,
        "height": 1920,
        "layout": "canvas",
        "platforms": ["TikTok", "Instagram Reels", "YouTube Shorts"],
    },
    "1x1": {
        "width": 1080,
        "height": 1080,
        "layout": "canvas",
        "platforms": ["Instagram feed", "LinkedIn"],
    },
    "4x5": {
        "width": 1080,
        "height": 1350,
        "layout": "canvas",
        "platforms": ["Instagram feed", "Facebook"],
    },
}

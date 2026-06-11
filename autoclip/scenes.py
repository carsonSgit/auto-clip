"""Visual scene boundary detection via PySceneDetect."""

from pathlib import Path


def detect_scene_boundaries(video_path: Path) -> list[float]:
    """Return sorted scene-change timestamps in seconds (excludes 0 and EOF)."""
    from scenedetect import ContentDetector, detect  # heavy import (cv2)

    scene_list = detect(str(video_path), ContentDetector())
    boundaries = sorted({round(start.get_seconds(), 3) for start, _ in scene_list} - {0.0})
    return boundaries

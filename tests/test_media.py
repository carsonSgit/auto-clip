import pytest

from autoclip import media
from autoclip.media import MediaError


def _probe_result(streams, duration="120.0", fps="30/1"):
    for s in streams:
        if s.get("codec_type") == "video":
            s.setdefault("width", 1920)
            s.setdefault("height", 1080)
            s.setdefault("avg_frame_rate", fps)
    return {"streams": streams, "format": {"duration": duration}}


def test_probe_video_parses_streams(monkeypatch):
    monkeypatch.setattr(
        media,
        "probe",
        lambda _p: _probe_result([{"codec_type": "video"}, {"codec_type": "audio"}]),
    )
    info = media.probe_video("anything.mp4")
    assert info == {"duration": 120.0, "width": 1920, "height": 1080, "fps": 30.0}


def test_probe_video_requires_video_stream(monkeypatch):
    monkeypatch.setattr(media, "probe", lambda _p: _probe_result([{"codec_type": "audio"}]))
    with pytest.raises(MediaError, match="No video stream"):
        media.probe_video("audio_only.m4a")


def test_probe_video_requires_audio_stream(monkeypatch):
    monkeypatch.setattr(media, "probe", lambda _p: _probe_result([{"codec_type": "video"}]))
    with pytest.raises(MediaError, match="No audio stream"):
        media.probe_video("silent.mp4")


def test_probe_video_requires_duration(monkeypatch):
    monkeypatch.setattr(
        media,
        "probe",
        lambda _p: _probe_result([{"codec_type": "video"}, {"codec_type": "audio"}], duration="0"),
    )
    with pytest.raises(MediaError, match="duration"):
        media.probe_video("zero.mp4")


def test_probe_video_handles_missing_frame_rate(monkeypatch):
    monkeypatch.setattr(
        media,
        "probe",
        lambda _p: _probe_result([{"codec_type": "video", "avg_frame_rate": "0/0"}, {"codec_type": "audio"}]),
    )
    assert media.probe_video("weird.mp4")["fps"] == 0.0

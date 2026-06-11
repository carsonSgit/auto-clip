"""Transcription behind a small interface.

MVP engine: faster-whisper (CPU int8) — gives segment + word timestamps without
the torch/pyannote stack. Swap in WhisperX here when Phase 2 adds diarization;
the transcript schema already carries an optional `speaker` field per segment.
"""

from pathlib import Path

from autoclip.config import settings


def transcribe(audio_wav: Path) -> dict:
    from faster_whisper import WhisperModel  # heavy import, keep out of web process

    model = WhisperModel(
        settings.whisper_model,
        device="cpu",
        compute_type=settings.whisper_compute_type,
    )
    segments_iter, info = model.transcribe(
        str(audio_wav),
        word_timestamps=True,
        vad_filter=True,
    )

    segments = []
    for i, seg in enumerate(segments_iter):
        segments.append({
            "id": i,
            "start": round(seg.start, 3),
            "end": round(seg.end, 3),
            "text": seg.text.strip(),
            "speaker": None,  # populated by diarization in Phase 2
            "words": [
                {"word": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3)}
                for w in (seg.words or [])
            ],
        })

    return {
        "language": info.language,
        "duration": round(info.duration, 3),
        "model": settings.whisper_model,
        "segments": segments,
    }

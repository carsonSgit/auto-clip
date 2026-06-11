# auto-clip

Internal tool: upload conference/event footage → automatic transcription, highlight
clipping, branding, captions, and platform-ready exports (9:16, 16:9, 1:1, 4:5).
Runs entirely locally with Docker — no cloud storage.

## Quick start

```bash
cp .env.example .env          # optionally set ANTHROPIC_API_KEY for LLM highlight selection
docker compose up --build
# open http://localhost:8000
```

Without an API key the pipeline still runs end-to-end using heuristic highlight
selection (scene boundaries + speech density).

## Test footage

```bash
docker compose run --rm web python scripts/fetch_test_footage.py
```

Downloads 1–2 public conference talks into `./data/samples/` — upload one via the UI.

## Outputs

`./data/outputs/<job_id>/` — `transcript.json`, then per clip: platform MP4s and post copy.

## Branding

Everything visual reads from `brandkit/brand.yaml` + `brandkit/assets/`. Swap in real
company logo/fonts/colors there; no code changes needed. Placeholder assets ship by default.

## Measured performance (i7-1360P, CPU-only)

A 12.4-min 1080p talk, cold run: ~3 min transcription (small int8, after one-time
~460MB model download) + ~2.5 min for scene detection, selection, and rendering
3 clips × 4 formats — about 0.5× source duration total.

## Notes

- CPU-only by design (dev laptop has no NVIDIA GPU). Whisper model defaults to
  `small` int8 via faster-whisper; tune with `WHISPER_MODEL` in `.env`.
  (faster-whisper is used instead of full WhisperX for a lean image — the
  transcriber abstraction in `autoclip/transcribe.py` is where WhisperX slots in
  when Phase 2 adds pyannote diarization.)
- Scratch media lives in named Docker volumes (fast WSL2 I/O); only `./data/outputs`
  and `./data/samples` are Windows-visible bind mounts.
- Full plan: see the approved MVP plan (day-by-day milestones, risks, acceptance criteria).

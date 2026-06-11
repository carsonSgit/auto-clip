"""Job orchestration.

One Celery task per job runs the stage functions sequentially, updating
Job.status between stages. With --concurrency=1 on a single laptop this is
simpler and easier to debug than a Celery chain, and a crash in any stage
lands in a single except block that records the error on the job.
"""

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from autoclip import media, scenes, transcribe
from autoclip.brand import load_brand
from autoclip.config import settings
from autoclip.db import SessionLocal, init_db
from autoclip.llm import selector
from autoclip.models import Clip, Job
from autoclip.pipeline.celery_app import celery_app
from autoclip.render.render import render_clip

logger = logging.getLogger(__name__)

EXCERPT_CHARS = 220


def _set_status(job_id: str, status: str, error: str | None = None, **fields) -> None:
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        job.status = status
        job.error = error
        for key, value in fields.items():
            setattr(job, key, value)
        session.commit()


def job_paths(job_id: str) -> dict[str, Path]:
    return {
        "upload": settings.uploads_dir / job_id,
        "work": settings.work_dir / job_id,
        "output": settings.output_dir / job_id,
    }


@celery_app.task(name="autoclip.run_job", bind=True, max_retries=1)
def run_job(self, job_id: str) -> None:
    init_db()
    paths = job_paths(job_id)
    paths["work"].mkdir(parents=True, exist_ok=True)
    paths["output"].mkdir(parents=True, exist_ok=True)

    try:
        with SessionLocal() as session:
            job = session.get(Job, job_id)
            params = {
                "context_text": job.context_text,
                "clip_count": job.clip_count,
                "min_clip_seconds": job.min_clip_seconds,
                "max_clip_seconds": job.max_clip_seconds,
                "source_filename": job.source_filename,
            }

        brand = load_brand()

        # --- Ingest ---
        _set_status(job_id, "ingesting")
        source = _find_source(paths["upload"])
        src_info = media.probe_video(source)
        _set_status(job_id, "transcribing", duration_seconds=src_info["duration"])

        # --- Transcribe (reuse prior transcript on re-runs) ---
        transcript_path = paths["output"] / "transcript.json"
        if transcript_path.is_file():
            transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
        else:
            audio = paths["work"] / "audio.wav"
            media.extract_audio(source, audio)
            transcript = transcribe.transcribe(audio)
            transcript_path.write_text(json.dumps(transcript, indent=2), encoding="utf-8")

        # --- Scene detection ---
        _set_status(job_id, "detecting_scenes")
        scene_boundaries = scenes.detect_scene_boundaries(source)

        # --- Highlight selection ---
        _set_status(job_id, "selecting_highlights")
        highlights, selector_used = selector.select_highlights(
            transcript, scene_boundaries,
            params["context_text"], brand.get("voice", ""),
            params["clip_count"], params["min_clip_seconds"], params["max_clip_seconds"],
        )
        if not highlights:
            raise RuntimeError("No usable highlights found (transcript may be empty or too short).")
        with SessionLocal() as session:
            session.query(Clip).filter_by(job_id=job_id).delete()  # idempotent re-runs
            for i, h in enumerate(highlights):
                session.add(Clip(
                    job_id=job_id, index=i,
                    start_seconds=float(h["start"]), end_seconds=float(h["end"]),
                    title=h["title"], rationale=h["rationale"],
                ))
            session.commit()
        _set_status(job_id, "rendering", selector_used=selector_used)

        # --- Render all formats per clip ---
        rendered: dict[int, dict[str, Path]] = {}
        for i, h in enumerate(highlights):
            clip_info = {"index": i, "start": h["start"], "end": h["end"], "title": h["title"]}
            outputs = render_clip(
                source, src_info, clip_info, transcript, brand,
                settings.brandkit_dir, paths["work"], paths["output"],
            )
            rendered[i] = outputs
            _mark_clip(job_id, i, "rendered")

        # --- Finalize: post copy + manifest ---
        _set_status(job_id, "finalizing")
        copy_inputs = [
            {"title": h["title"], "excerpt": _excerpt(transcript, h["start"], h["end"])}
            for h in highlights
        ]
        post_copy = selector.generate_post_copy(
            copy_inputs, params["context_text"], brand.get("voice", "")
        )
        _write_post_copy(paths["output"] / "post_copy.md", highlights, post_copy)
        _write_manifest(
            paths["output"] / "manifest.json",
            job_id, params, src_info, selector_used, highlights, rendered, post_copy, brand,
        )

        _set_status(job_id, "complete")
    except Exception as exc:
        logger.exception("Job %s failed (attempt %s)", job_id, self.request.retries + 1)
        if self.request.retries < self.max_retries:
            # One automatic retry; transcript reuse makes it cheap. Status stays
            # visible to the user while the retry waits.
            _set_status(job_id, "queued", error=f"Retrying after: {type(exc).__name__}: {exc}")
            _cleanup_work(paths["work"])
            raise self.retry(exc=exc, countdown=15)
        _set_status(job_id, "failed", error=f"{type(exc).__name__}: {exc}")
    finally:
        _cleanup_work(paths["work"])


def _mark_clip(job_id: str, index: int, status: str) -> None:
    with SessionLocal() as session:
        clip = session.query(Clip).filter_by(job_id=job_id, index=index).one()
        clip.status = status
        session.commit()


def _excerpt(transcript: dict, start: float, end: float) -> str:
    text = " ".join(
        s["text"] for s in transcript["segments"] if s["start"] < end and s["end"] > start
    )
    return text[:EXCERPT_CHARS] + ("…" if len(text) > EXCERPT_CHARS else "")


def _write_post_copy(dest: Path, highlights: list[dict], post_copy: dict) -> None:
    lines = ["# Post copy", ""]
    for i, h in enumerate(highlights):
        lines += [f"## Clip {i}: {h['title']}", ""]
        for platform, copy in post_copy.get(str(i), {}).items():
            lines += [f"### {platform}", "", copy, ""]
    dest.write_text("\n".join(lines), encoding="utf-8")


def _write_manifest(
    dest: Path, job_id: str, params: dict, src_info: dict, selector_used: str,
    highlights: list[dict], rendered: dict, post_copy: dict, brand: dict,
) -> None:
    manifest = {
        "job_id": job_id,
        "source_filename": params["source_filename"],
        "source": src_info,
        "brand": brand.get("name"),
        "selector": selector_used,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "clips": [
            {
                **h,
                "index": i,
                "files": {fmt: f"clip_{i}/{path.name}" for fmt, path in rendered.get(i, {}).items()},
                "post_copy": post_copy.get(str(i), {}),
            }
            for i, h in enumerate(highlights)
        ],
    }
    dest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _find_source(upload_dir: Path) -> Path:
    files = [p for p in upload_dir.iterdir() if p.is_file()]
    if not files:
        raise FileNotFoundError(f"No uploaded file found in {upload_dir}")
    return files[0]


def _cleanup_work(work_dir: Path) -> None:
    shutil.rmtree(work_dir, ignore_errors=True)

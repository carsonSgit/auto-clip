import errno
import re
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import BinaryIO

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, text

from autoclip.config import settings
from autoclip.db import SessionLocal, init_db
from autoclip.models import Job
from autoclip.pipeline.celery_app import celery_app


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="auto-clip", lifespan=lifespan)
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
settings.output_dir.mkdir(parents=True, exist_ok=True)  # StaticFiles needs it at mount time
app.mount("/outputs", StaticFiles(directory=settings.output_dir), name="outputs")

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".mts"}
# Job ids are uuid4().hex (32 lowercase hex chars). Validating the shape before
# touching the DB or filesystem keeps untrusted path segments out of file paths.
_JOB_ID_RE = re.compile(r"\A[0-9a-f]{32}\Z")
_UPLOAD_CHUNK = 1024 * 1024


class _UploadTooLarge(Exception):
    """Raised when an upload exceeds settings.max_upload_bytes mid-stream."""


class _UploadStorageFull(Exception):
    """Raised when the upload volume runs out of free space mid-stream."""


def _valid_job_id(job_id: str) -> bool:
    return bool(_JOB_ID_RE.match(job_id))


def _error(request: Request, message: str, status_code: int):
    return templates.TemplateResponse(request, "error.html", {"message": message}, status_code=status_code)


def _save_upload(src: BinaryIO, dest: Path, max_bytes: int) -> int:
    """Stream an upload to disk, aborting if it exceeds max_bytes. Returns bytes written."""
    total = 0
    try:
        with dest.open("wb") as out:
            while chunk := src.read(_UPLOAD_CHUNK):
                total += len(chunk)
                if total > max_bytes:
                    raise _UploadTooLarge
                out.write(chunk)
    except OSError as exc:
        if exc.errno == errno.ENOSPC:
            raise _UploadStorageFull from exc
        raise
    return total


def _has_upload_capacity(upload_root: Path, upload_bytes: int) -> bool:
    """Return whether the upload volume has enough free space for upload plus processing headroom."""
    required = upload_bytes + settings.upload_free_space_reserve_bytes
    usage_root = upload_root
    while not usage_root.exists() and usage_root != usage_root.parent:
        usage_root = usage_root.parent
    return shutil.disk_usage(usage_root).free >= required


def _job_dict(job: Job) -> dict:
    return {
        "id": job.id,
        "source_filename": job.source_filename,
        "status": job.status,
        "error": job.error,
        "duration_seconds": job.duration_seconds,
        "selector_used": job.selector_used,
        "created_at": job.created_at.strftime("%Y-%m-%d %H:%M"),
        "clips": [
            {
                "index": c.index,
                "title": c.title,
                "start_seconds": c.start_seconds,
                "end_seconds": c.end_seconds,
                "status": c.status,
            }
            for c in job.clips
        ],
    }


@app.get("/healthz")
def healthz():
    """Liveness/readiness probe: confirms the database is reachable."""
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ok"}


@app.get("/")
def index(request: Request):
    with SessionLocal() as session:
        jobs = session.scalars(select(Job).order_by(Job.created_at.desc()).limit(50)).all()
        job_dicts = [_job_dict(j) for j in jobs]
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "jobs": job_dicts,
            "defaults": {
                "clip_count": settings.default_clip_count,
                "min_clip_seconds": settings.min_clip_seconds,
                "max_clip_seconds": settings.max_clip_seconds,
            },
        },
    )


@app.post("/jobs")
def create_job(
    request: Request,
    file: UploadFile,
    context_text: str = Form(""),
    clip_count: int = Form(4),
    min_clip_seconds: int = Form(20),
    max_clip_seconds: int = Form(90),
):
    suffix = Path(file.filename or "upload").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        return _error(request, f"Unsupported file type '{suffix}'. Allowed: {allowed}", 400)

    too_large = f"File too large. Maximum upload size is {settings.max_upload_mb} MB."
    if file.size is not None and file.size > settings.max_upload_bytes:
        return _error(request, too_large, 413)
    storage_full = "Upload storage is full. Please delete old jobs or reduce the upload size and try again."
    if file.size is not None and not _has_upload_capacity(settings.uploads_dir, file.size):
        return _error(request, storage_full, 507)

    job_id = uuid.uuid4().hex
    upload_dir = settings.uploads_dir / job_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / f"source{suffix}"
    try:
        _save_upload(file.file, dest, settings.max_upload_bytes)
    except _UploadTooLarge:
        shutil.rmtree(upload_dir, ignore_errors=True)
        return _error(request, too_large, 413)
    except _UploadStorageFull:
        shutil.rmtree(upload_dir, ignore_errors=True)
        return _error(request, storage_full, 507)

    job = Job(
        id=job_id,
        source_filename=(file.filename or "upload")[:512],  # fits source_filename column
        context_text=context_text.strip(),
        clip_count=max(1, min(clip_count, 10)),
        min_clip_seconds=max(5, min_clip_seconds),
        max_clip_seconds=max(min_clip_seconds + 5, max_clip_seconds),
    )
    with SessionLocal() as session:
        session.add(job)
        session.commit()

    celery_app.send_task("autoclip.run_job", args=[job_id])
    return RedirectResponse(url=f"/jobs/{job_id}", status_code=303)


@app.get("/jobs/{job_id}")
def job_detail(request: Request, job_id: str):
    if not _valid_job_id(job_id):
        return _error(request, "Job not found.", 404)
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        if job is None:
            return _error(request, "Job not found.", 404)
        job_data = _job_dict(job)
    outputs = _list_outputs(job_id)
    return templates.TemplateResponse(request, "job.html", {"job": job_data, "outputs": outputs})


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    if not _valid_job_id(job_id):
        raise HTTPException(status_code=404, detail="job not found")
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return _job_dict(job)


def _list_outputs(job_id: str) -> list[dict]:
    """Files under /outputs/<job_id>, as url+label pairs for the job page."""
    root = settings.output_dir / job_id
    if not root.is_dir():
        return []
    files = sorted(p for p in root.rglob("*") if p.is_file())
    return [
        {
            "url": f"/outputs/{job_id}/{p.relative_to(root).as_posix()}",
            "label": p.relative_to(root).as_posix(),
        }
        for p in files
    ]

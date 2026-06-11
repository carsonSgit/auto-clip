import shutil
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

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
settings.output_dir.mkdir(parents=True, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=settings.output_dir), name="outputs")

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".mts"}


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


@app.get("/")
def index(request: Request):
    with SessionLocal() as session:
        jobs = session.scalars(select(Job).order_by(Job.created_at.desc()).limit(50)).all()
        job_dicts = [_job_dict(j) for j in jobs]
    return templates.TemplateResponse(request, "index.html", {
        "jobs": job_dicts,
        "defaults": {
            "clip_count": settings.default_clip_count,
            "min_clip_seconds": settings.min_clip_seconds,
            "max_clip_seconds": settings.max_clip_seconds,
        },
    })


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
        return templates.TemplateResponse(
            request, "error.html",
            {"message": f"Unsupported file type '{suffix}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"},
            status_code=400,
        )

    job = Job(
        source_filename=file.filename or "upload",
        context_text=context_text.strip(),
        clip_count=max(1, min(clip_count, 10)),
        min_clip_seconds=max(5, min_clip_seconds),
        max_clip_seconds=max(min_clip_seconds + 5, max_clip_seconds),
    )
    upload_dir = settings.uploads_dir / job.id
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / f"source{suffix}"
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out, length=1024 * 1024)

    with SessionLocal() as session:
        session.add(job)
        session.commit()

    celery_app.send_task("autoclip.run_job", args=[job.id])
    return RedirectResponse(url=f"/jobs/{job.id}", status_code=303)


@app.get("/jobs/{job_id}")
def job_detail(request: Request, job_id: str):
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        if job is None:
            return templates.TemplateResponse(
                request, "error.html", {"message": "Job not found."}, status_code=404,
            )
        job_data = _job_dict(job)
    outputs = _list_outputs(job_id)
    return templates.TemplateResponse(request, "job.html", {"job": job_data, "outputs": outputs})


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        if job is None:
            return {"error": "not found"}
        return _job_dict(job)


def _list_outputs(job_id: str) -> list[dict]:
    """Files under /outputs/<job_id>, as url+label pairs for the job page."""
    root = settings.output_dir / job_id
    if not root.is_dir():
        return []
    files = sorted(p for p in root.rglob("*") if p.is_file())
    return [
        {"url": f"/outputs/{job_id}/{p.relative_to(root).as_posix()}", "label": p.relative_to(root).as_posix()}
        for p in files
    ]

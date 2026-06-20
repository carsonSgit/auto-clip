import io

import pytest
from fastapi.testclient import TestClient

from autoclip.config import settings
from autoclip.db import init_db
from autoclip.web import app as web_app
from autoclip.web.app import (
    _has_upload_capacity,
    _save_upload,
    _UploadStorageFull,
    _UploadTooLarge,
    _valid_job_id,
)


@pytest.fixture
def client(monkeypatch):
    sent = []
    monkeypatch.setattr(
        web_app.celery_app, "send_task", lambda name, args=None, **kw: sent.append((name, args))
    )
    init_db()
    c = TestClient(web_app.app)
    c.sent_tasks = sent
    return c


def test_index_renders(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"New job" in resp.content


def test_rejects_unsupported_extension(client):
    resp = client.post(
        "/jobs",
        files={"file": ("notes.txt", io.BytesIO(b"x"), "text/plain")},
    )
    assert resp.status_code == 400
    assert b"Unsupported file type" in resp.content
    assert client.sent_tasks == []


def test_create_job_happy_path(client):
    resp = client.post(
        "/jobs",
        files={"file": ("talk.mp4", io.BytesIO(b"fake"), "video/mp4")},
        data={
            "context_text": "DevConf",
            "clip_count": "3",
            "min_clip_seconds": "20",
            "max_clip_seconds": "60",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    location = resp.headers["location"]
    job_id = location.split("/jobs/")[1]
    assert len(client.sent_tasks) == 1
    task_name, task_args = client.sent_tasks[0]
    assert task_name == "autoclip.run_job"
    assert task_args == [job_id]
    assert (settings.uploads_dir / job_id / "source.mp4").is_file()


def test_job_status_api(client):
    # Create a job first
    resp = client.post(
        "/jobs",
        files={"file": ("talk.mp4", io.BytesIO(b"fake"), "video/mp4")},
        follow_redirects=False,
    )
    job_id = resp.headers["location"].split("/jobs/")[1]

    api_resp = client.get(f"/api/jobs/{job_id}")
    assert api_resp.status_code == 200
    data = api_resp.json()
    assert data["status"] == "queued"
    assert data["source_filename"] == "talk.mp4"


def test_job_status_unknown_is_404(client):
    resp = client.get("/api/jobs/nope")
    assert resp.status_code == 404


def test_job_page_unknown_is_404(client):
    resp = client.get("/jobs/nope")
    assert resp.status_code == 404


def test_healthz_ok(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_upload_rejected_when_too_large(client, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_mb", 0)  # any non-empty file exceeds the limit
    resp = client.post(
        "/jobs",
        files={"file": ("talk.mp4", io.BytesIO(b"some bytes"), "video/mp4")},
        follow_redirects=False,
    )
    assert resp.status_code == 413
    assert b"too large" in resp.content.lower()
    assert client.sent_tasks == []  # no job queued


def test_upload_storage_full_is_reported_and_cleaned_up(client, monkeypatch):
    job_id = "a" * 32
    monkeypatch.setattr(web_app.uuid, "uuid4", lambda: type("FakeUUID", (), {"hex": job_id})())
    monkeypatch.setattr(
        web_app,
        "_save_upload",
        lambda *args, **kwargs: (_ for _ in ()).throw(_UploadStorageFull),
    )

    resp = client.post(
        "/jobs",
        files={"file": ("talk.mp4", io.BytesIO(b"some bytes"), "video/mp4")},
        follow_redirects=False,
    )

    assert resp.status_code == 507
    assert b"storage is full" in resp.content.lower()
    assert not (settings.uploads_dir / job_id).exists()
    assert client.sent_tasks == []


def test_has_upload_capacity_keeps_processing_reserve(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "upload_free_space_reserve_mb", 1)
    monkeypatch.setattr(
        web_app.shutil,
        "disk_usage",
        lambda path: type("Usage", (), {"free": 2_000_000})(),
    )

    assert _has_upload_capacity(tmp_path, 900_000)
    assert not _has_upload_capacity(tmp_path, 1_100_000)


def test_has_upload_capacity_uses_existing_parent_for_missing_upload_dir(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(settings, "upload_free_space_reserve_mb", 1)
    monkeypatch.setattr(
        web_app.shutil,
        "disk_usage",
        lambda path: seen.append(path) or type("Usage", (), {"free": 2_000_000})(),
    )

    assert _has_upload_capacity(tmp_path / "data" / "uploads", 900_000)
    assert seen == [tmp_path]


@pytest.mark.parametrize(
    ("job_id", "expected"),
    [
        ("a" * 32, True),
        ("0123456789abcdef0123456789abcdef", True),
        ("A" * 32, False),  # uppercase is not produced by uuid4().hex
        ("a" * 31, False),  # too short
        ("a" * 33, False),  # too long
        ("../etc/passwd", False),  # path traversal attempt
        ("", False),
    ],
)
def test_valid_job_id(job_id, expected):
    assert _valid_job_id(job_id) is expected


def test_save_upload_aborts_when_too_large(tmp_path):
    dest = tmp_path / "out.bin"
    with pytest.raises(_UploadTooLarge):
        _save_upload(io.BytesIO(b"x" * 1000), dest, max_bytes=100)


def test_save_upload_reports_no_space_left(monkeypatch, tmp_path):
    class FullDiskFile:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def write(self, chunk):
            raise OSError(28, "No space left on device")

    monkeypatch.setattr(web_app.Path, "open", lambda *args, **kwargs: FullDiskFile())

    with pytest.raises(_UploadStorageFull):
        _save_upload(io.BytesIO(b"x"), tmp_path / "out.bin", max_bytes=100)


def test_save_upload_writes_full_file(tmp_path):
    dest = tmp_path / "out.bin"
    payload = b"hello world" * 10
    written = _save_upload(io.BytesIO(payload), dest, max_bytes=10_000)
    assert written == len(payload)
    assert dest.read_bytes() == payload

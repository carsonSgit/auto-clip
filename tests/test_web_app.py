import io

import pytest
from fastapi.testclient import TestClient

from autoclip.config import settings
from autoclip.db import init_db
from autoclip.web import app as web_app


@pytest.fixture
def client(monkeypatch):
    sent = []
    monkeypatch.setattr(web_app.celery_app, "send_task",
                        lambda name, args=None, **kw: sent.append((name, args)))
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

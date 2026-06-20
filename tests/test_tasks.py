from autoclip.db import SessionLocal, init_db
from autoclip.models import Job
from autoclip.pipeline import tasks


def test_set_status_updates_job():
    init_db()
    with SessionLocal() as session:
        job = Job(source_filename="t.mp4")
        session.add(job)
        session.commit()
        job_id = job.id

    tasks._set_status(job_id, "rendering", selector_used="heuristic")

    with SessionLocal() as session:
        job = session.get(Job, job_id)
        assert job.status == "rendering"
        assert job.selector_used == "heuristic"


def test_set_status_missing_job_is_noop():
    init_db()
    # Must not raise even though the job does not exist.
    tasks._set_status("0" * 32, "complete")


def test_cleanup_upload_removes_upload_dir(tmp_path):
    upload_dir = tmp_path / "uploads" / "job"
    upload_dir.mkdir(parents=True)
    (upload_dir / "source.mp4").write_bytes(b"video")

    tasks._cleanup_upload(upload_dir)

    assert not upload_dir.exists()


def test_excerpt_truncates_long_text():
    segments = [{"start": 0.0, "end": 100.0, "text": "word " * 200}]
    transcript = {"segments": segments}
    excerpt = tasks._excerpt(transcript, 0.0, 100.0)
    assert excerpt.endswith("…")
    assert len(excerpt) <= tasks.EXCERPT_CHARS + 1


def test_excerpt_only_includes_overlapping_segments():
    transcript = {
        "segments": [
            {"start": 0.0, "end": 10.0, "text": "before"},
            {"start": 20.0, "end": 30.0, "text": "inside"},
            {"start": 90.0, "end": 100.0, "text": "after"},
        ]
    }
    excerpt = tasks._excerpt(transcript, 15.0, 35.0)
    assert excerpt == "inside"

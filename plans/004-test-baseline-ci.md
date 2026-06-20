# Plan 004: Test the web layer and LLM-output sanitizers; add CI

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat 60ecfba..HEAD -- autoclip/web/app.py autoclip/llm/anthropic_provider.py tests/ requirements.txt`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition. (Plan 002 intentionally changes
> `app.py`'s `job_status` to raise a 404 — that exact change is expected and
> required, not drift.)

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: LOW (additive: new tests, one dev dependency, a CI workflow; no
  production code changes)
- **Depends on**: plans/002-api-job-status-404.md (one new test asserts the
  404 behavior that plan introduces)
- **Category**: tests
- **Planned at**: commit `60ecfba`, 2026-06-11

## Why this matters

The existing 13 tests cover only pure helpers (ffmpeg command building,
layout, subtitles, heuristic selection, brand loading). Zero coverage exists
for:

- **The web layer** (`autoclip/web/app.py`): upload validation, job creation,
  the status API — the only user-facing surface.
- **The LLM-output sanitizers** (`autoclip/llm/anthropic_provider.py`:
  `_extract_json`, `_sanitize_highlights`): the code that defends the
  pipeline against malformed model output. These are pure functions taking
  untrusted input — the highest-value unit-test targets in the repo — and a
  regression here silently degrades every LLM-selected job.

There is also no CI: tests only run when someone remembers to run them. A
minimal GitHub Actions workflow makes `pytest` the gate for every push.

## Current state

- Tests live in `tests/`, plain pytest functions, shared fixtures in
  `tests/conftest.py` (provides `transcript` — a synthetic 120s talk — and
  `brand`). Pattern files: `tests/test_heuristic.py`, `tests/test_ffmpeg_cmds.py`.
- `tests/conftest.py` currently starts directly with `import pytest` —
  there is no environment setup, because no existing test touches settings,
  the DB, or the filesystem.
- `autoclip/config.py` — `settings = Settings()` is instantiated at module
  import; `pydantic_settings.BaseSettings` reads env vars case-insensitively
  (`DATABASE_URL` → `database_url`, `DATA_DIR` → `data_dir`, `OUTPUT_DIR` →
  `output_dir`). Defaults point at Docker paths (`/data`, `/outputs`) and the
  compose Postgres — **tests must override these via env vars before any
  `autoclip` import**.
- `autoclip/db.py` — engine and `SessionLocal` are created at import from
  `settings.database_url`; `init_db()` runs `create_all`.
- `autoclip/web/app.py` — module import mounts
  `StaticFiles(directory=settings.output_dir)` (line 29), so `OUTPUT_DIR`
  must exist before import; line 28 mkdirs it. Job creation (lines 71–107)
  validates the extension against `ALLOWED_EXTENSIONS`, writes the upload to
  `settings.uploads_dir / job.id / f"source{suffix}"`, commits a `Job` row,
  then calls `celery_app.send_task("autoclip.run_job", args=[job.id])` and
  303-redirects to `/jobs/{job.id}`.
- `autoclip/llm/anthropic_provider.py` — the two sanitizers:

```python
def _extract_json(text: str):                                  # lines 73–80
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1].lstrip("json").strip()
    start = min((i for i in (text.find("["), text.find("{")) if i >= 0), default=-1)
    if start < 0:
        raise ValueError("no JSON found in response")
    return json.loads(text[start:])
```

  `_sanitize_highlights(data, transcript, clip_count, min_seconds, max_seconds)`
  (lines 118–147) clamps starts/ends to media duration, snaps them to the
  nearest segment start/end, drops items shorter than `min_seconds * 0.5` or
  longer than `max_seconds * 1.5`, drops overlaps (first-by-start wins),
  truncates titles to 200 chars, raises `ValueError` if nothing survives,
  returns at most `clip_count` items. Importing the module needs only
  `jsonschema` + settings (the `anthropic` import is lazy, inside `_client`).
- `requirements.txt` — single flat file, pinned `==X.Y.*` style; `pytest==8.*`
  is already in it. FastAPI's `TestClient` requires `httpx`, which is **not**
  yet listed.
- No `.github/` directory exists.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Tests (canonical, in Docker) | `docker compose run --rm web python -m pytest -q` | all pass, exit 0 |
| Rebuild after requirements change | `docker compose build web` | exit 0 |
| CI syntax check (optional, if `gh` or `act` absent, skip) | — | — |

## Scope

**In scope** (the only files you should modify/create):
- `tests/conftest.py` (prepend env setup; keep existing fixtures untouched)
- `tests/test_web_app.py` (create)
- `tests/test_llm_sanitize.py` (create)
- `requirements.txt` (add `httpx==0.27.*` next to `pytest`)
- `.github/workflows/ci.yml` (create)

**Out of scope** (do NOT touch):
- `autoclip/**` — this plan is purely additive tests/CI; if a test exposes a
  bug in app code, report it, don't fix it here.
- `docker-compose.yml`, `docker/Dockerfile`.
- Testing `autoclip/pipeline/tasks.py` — needs ffmpeg/whisper fakes; too
  large for this plan, deliberately deferred.

## Git workflow

- Branch: `advisor/004-test-baseline-ci`
- Commit per step or one combined commit; message style matches repo history
  (imperative, no prefix), e.g. "Add web-layer and LLM-sanitizer tests plus CI".
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Test environment setup in `tests/conftest.py`

At the **very top** of `tests/conftest.py`, before `import pytest` and before
anything imports `autoclip`, add:

```python
import os
import tempfile

# Must run before any autoclip import: settings is built at import time.
_TMP = tempfile.mkdtemp(prefix="autoclip-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["DATA_DIR"] = os.path.join(_TMP, "data")
os.environ["OUTPUT_DIR"] = os.path.join(_TMP, "outputs")
```

Note: plain assignment, not `setdefault` — inside Docker the compose file
sets `DATABASE_URL` to the real Postgres, and tests must never write jobs
into the dev database.

**Verify**: `docker compose run --rm web python -m pytest -q` → existing
tests still pass.

### Step 2: Add `httpx` and rebuild

Add `httpx==0.27.*` to `requirements.txt` (after `pytest==8.*`). Rebuild:
`docker compose build web`.

**Verify**: `docker compose run --rm web python -c "from fastapi.testclient import TestClient; print('ok')"` → `ok`

### Step 3: Web-layer tests — `tests/test_web_app.py`

Create the file. Required scaffolding inside it:

```python
import io

import pytest
from fastapi.testclient import TestClient

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
```

Test cases (plain functions, one assertion theme each):

1. `test_index_renders` — `client.get("/")` → 200, `b"New job"` in body.
2. `test_rejects_unsupported_extension` — POST `/jobs` multipart with
   `files={"file": ("notes.txt", io.BytesIO(b"x"), "text/plain")}` →
   status 400, body mentions "Unsupported file type"; `client.sent_tasks`
   empty.
3. `test_create_job_happy_path` — POST `/jobs` with
   `files={"file": ("talk.mp4", io.BytesIO(b"fake"), "video/mp4")}` and
   `data={"context_text": "DevConf", "clip_count": "3", "min_clip_seconds": "20", "max_clip_seconds": "60"}`,
   with `follow_redirects=False` → status 303; extract the job id from the
   `location` header (`/jobs/<id>`); assert exactly one entry in
   `client.sent_tasks` named `"autoclip.run_job"` with `args=[<id>]`; assert
   `(settings.uploads_dir / <id> / "source.mp4").is_file()` (import
   `settings` from `autoclip.config`).
4. `test_job_status_api` — after a happy-path POST, `client.get(f"/api/jobs/{id}")`
   → 200, JSON `status == "queued"`, `source_filename == "talk.mp4"`.
5. `test_job_status_unknown_is_404` — `client.get("/api/jobs/nope")` → 404.
   (Requires plan 002; see STOP conditions.)
6. `test_job_page_unknown_is_404` — `client.get("/jobs/nope")` → 404.

**Verify**: `docker compose run --rm web python -m pytest tests/test_web_app.py -q`
→ 6 passed.

### Step 4: Sanitizer tests — `tests/test_llm_sanitize.py`

Create the file, importing `_extract_json` and `_sanitize_highlights` from
`autoclip.llm.anthropic_provider`. Cases:

For `_extract_json`:
1. plain JSON array → parsed list.
2. fenced block (`"```json\n[1, 2]\n```"`) → `[1, 2]`.
3. prose before the JSON (`'Here you go: {"a": 1}'`) → `{"a": 1}`.
4. no JSON at all (`"sorry, I cannot"`) → raises `ValueError`.

For `_sanitize_highlights` (reuse the `transcript` fixture from conftest —
120s, segments every 5s with a 50–70s silence gap; `min_seconds=10`,
`max_seconds=30`, `clip_count=3` unless stated):
5. valid item (`{"start": 0.0, "end": 25.0, ...}`) survives, start/end
   snapped to segment boundaries (floats from the fixture grid).
6. `end` beyond duration (e.g. `500`) is clamped to ≤ 120 and snapped.
7. item shorter than `min_seconds * 0.5` (e.g. 0→4s) is dropped.
8. two overlapping items → only the earlier-starting one survives.
9. all items unusable → raises `ValueError`.
10. more than `clip_count` valid items → result truncated to `clip_count`.

Every input item must include `"title"` and `"rationale"` strings (the
function reads both).

**Verify**: `docker compose run --rm web python -m pytest tests/test_llm_sanitize.py -q`
→ 10 passed.

### Step 5: CI workflow — `.github/workflows/ci.yml`

```yaml
name: ci
on:
  push:
  pull_request:
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - run: pip install -r requirements.txt
      - run: python -m pytest -q
```

(Full `requirements.txt` install is deliberate: the heavy deps —
faster-whisper, opencv — are lazily imported and not exercised, but a partial
install list would rot. Pip cache keeps repeat runs fast.)

**Verify**: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`
→ exit 0 (valid YAML). Actual workflow run happens on next push — out of
scope here.

### Step 6: Full suite

**Verify**: `docker compose run --rm web python -m pytest -q` → all pass;
count ≥ 29 (13 pre-existing + 16 new; if plan 003 landed first, +5 more).

## Test plan

This plan *is* the test plan — see Steps 3–4. Pattern files:
`tests/test_heuristic.py` (pure-function style), `tests/conftest.py`
(fixtures).

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `docker compose run --rm web python -m pytest -q` exits 0, ≥ 29 tests
- [ ] `tests/test_web_app.py` and `tests/test_llm_sanitize.py` exist with the
      cases listed (6 + 10)
- [ ] `grep -n httpx requirements.txt` → one match
- [ ] `.github/workflows/ci.yml` exists and parses as YAML
- [ ] `git status` shows no modified files outside the in-scope list
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- `client.get("/api/jobs/nope")` returns **200**: plan 002 has not landed.
  Either execute 002 first (if you were told to) or stop and report the
  dependency.
- Importing `autoclip.web.app` fails under the sqlite env override (would
  mean a hard Postgres dependency was added since planning).
- Any test failure that looks like an app bug rather than a test bug —
  report the bug, do not patch `autoclip/**`.
- `tests/conftest.py` no longer matches its described shape (drifted).

## Maintenance notes

- The env override in `conftest.py` must stay at the top of the file, before
  autoclip imports — a future "tidy imports" pass could silently break it;
  the plain-assignment comment guards against reverting to `setdefault`.
- When Phase 2 adds diarization/WhisperX, `tasks.py` orchestration tests
  (deferred here) become worth a dedicated plan with ffmpeg/whisper fakes.
- CI installs full requirements (~2–3 min cold); if that grows painful, split
  a `requirements-dev.txt` then — not before.

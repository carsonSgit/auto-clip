# Plan 001: Stop Redis redelivering long-running jobs (visibility timeout)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat 60ecfba..HEAD -- autoclip/pipeline/celery_app.py tests/`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: bug
- **Planned at**: commit `60ecfba`, 2026-06-11

## Why this matters

The Celery app uses Redis as broker with `task_acks_late=True`. With acks-late,
the task message is only acknowledged when the task *finishes*. The Redis
transport has a default `visibility_timeout` of **3600 seconds (1 hour)**: any
message unacked for longer than that is restored to the queue and delivered
again.

A job in this app runs transcription + scene detection + rendering as **one
task**, measured at roughly 0.5× source duration on the target machine (see
`README.md` "Measured performance"). A source video longer than ~2 hours —
entirely plausible for the conference/event recordings this tool exists for —
therefore exceeds 1 hour of task runtime. The message gets redelivered, and
with `--concurrency=1` the worker re-runs the *entire job* right after
finishing it: status flips back to "ingesting", scene detection and all
renders are redone, outputs and manifest are rewritten. The user sees a
completed job spontaneously go back to "rendering".

The fix is a one-line broker transport option raising the visibility timeout
far above any realistic job duration.

## Current state

- `autoclip/pipeline/celery_app.py` — the only Celery configuration in the
  repo. Full current content (17 lines):

```python
from celery import Celery

from autoclip.config import settings

celery_app = Celery(
    "autoclip",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["autoclip.pipeline.tasks"],
)

celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
)
```

- `autoclip/pipeline/tasks.py:47` — the single task,
  `@celery_app.task(name="autoclip.run_job", bind=True, max_retries=1)`,
  runs the whole pipeline for one job. Do not modify it in this plan.
- Repo convention: short inline comments explaining *why* a config value
  exists (see `render_parallelism` in `autoclip/config.py:20`). Match that.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Tests (canonical, in Docker) | `docker compose run --rm web python -m pytest -q` | all pass, exit 0 |
| Config check | `docker compose run --rm web python -c "from autoclip.pipeline.celery_app import celery_app; print(celery_app.conf.broker_transport_options)"` | `{'visibility_timeout': 43200}` |

If Docker is unavailable, a host venv with `pip install celery[redis] pydantic-settings`
is enough for the config check (`python -c ...` same as above); the import does
not connect to Redis.

## Scope

**In scope** (the only files you should modify):
- `autoclip/pipeline/celery_app.py`

**Out of scope** (do NOT touch, even though they look related):
- `autoclip/pipeline/tasks.py` — retry/status logic is separate and verified.
- `docker-compose.yml` — no infra change needed.
- `task_acks_late` itself — it is intentional (worker crash → job redelivered
  after the timeout instead of lost). Do not set it to False.

## Git workflow

- Branch: `advisor/001-celery-visibility-timeout`
- Single commit; message style matches repo history (imperative, no prefix),
  e.g. "Raise Redis visibility timeout above max job runtime".
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Add the broker transport option

In `autoclip/pipeline/celery_app.py`, extend the existing `conf.update(...)`
call with:

```python
    # acks_late + Redis: unacked messages are redelivered after
    # visibility_timeout. Default is 1h; a job runs ~0.5x source duration,
    # so long event recordings would be silently re-run. 12h clears any
    # realistic job while still recovering from a crashed worker.
    broker_transport_options={"visibility_timeout": 43200},
```

**Verify**: `docker compose run --rm web python -c "from autoclip.pipeline.celery_app import celery_app; print(celery_app.conf.broker_transport_options)"`
→ prints `{'visibility_timeout': 43200}`

### Step 2: Run the test suite

**Verify**: `docker compose run --rm web python -m pytest -q` → all tests pass
(13 at planning time), exit 0.

## Test plan

No new test file: the change is a static config value with no behavior
observable in-process. The config-check command in Step 1 is the regression
gate; record its output in your report.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] Config check command prints `{'visibility_timeout': 43200}`
- [ ] `docker compose run --rm web python -m pytest -q` exits 0
- [ ] `git status` shows only `autoclip/pipeline/celery_app.py` (and
      `plans/README.md`) modified
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- `celery_app.py` no longer matches the excerpt above (drifted).
- `celery_app.conf.broker_transport_options` already contains a
  `visibility_timeout` — someone fixed this independently; mark the plan
  REJECTED in the index with that note.
- The test suite fails *before* your change (broken baseline is not yours to
  fix here).

## Maintenance notes

- If jobs ever legitimately exceed ~12h (e.g. batch multi-video jobs), raise
  the value again — symptom is the same silent re-run loop.
- If the broker is ever switched off Redis (e.g. to RabbitMQ), this option is
  ignored and can be removed; RabbitMQ has no visibility-timeout redelivery.
- Reviewer should confirm `task_acks_late=True` was kept.

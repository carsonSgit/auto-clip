# Plan 002: Return real 404s from the job-status API (kills a reload loop)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat 60ecfba..HEAD -- autoclip/web/`
> NOTE: at planning time `autoclip/web/templates/base.html` and `job.html`
> already had **uncommitted working-tree changes**; the excerpts below were
> taken from the working tree, not the commit. Compare excerpts against the
> live files; on a mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: bug
- **Planned at**: commit `60ecfba` (+ uncommitted template edits), 2026-06-11

## Why this matters

`GET /api/jobs/{job_id}` returns `{"error": "not found"}` with HTTP **200**
when the job doesn't exist. The job page's polling script only bails on
non-OK responses (`if (!res.ok) return;`), so for a missing job it proceeds:
`data.status` is `undefined`, which never equals the status pill's text, and
the script's "status changed" branch fires `location.reload()`. The reloaded
page polls again → **infinite reload loop** for any job page whose row has
been deleted (e.g. after a future DB wipe or admin cleanup), and any
programmatic API consumer can't distinguish "missing" from a real payload
without sniffing the body. Returning a proper 404 fixes both: the existing
`!res.ok` guard then stops polling for free.

## Current state

- `autoclip/web/app.py` — FastAPI app. The endpoint at lines 123–129:

```python
@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        if job is None:
            return {"error": "not found"}
        return _job_dict(job)
```

- `autoclip/web/templates/job.html` — polling script (working-tree version,
  lines 41–56):

```html
<script>
  const TERMINAL = ["complete", "failed", "transcribed"];
  async function poll() {
    const res = await fetch(`/api/jobs/{{ job.id }}`);
    if (!res.ok) return;
    const data = await res.json();
    const pill = document.getElementById("status-pill");
    if (data.status !== pill.textContent) {
      // Stage changed: reload so clips/outputs/error sections re-render.
      location.reload();
      return;
    }
    if (!TERMINAL.includes(data.status)) setTimeout(poll, 3000);
  }
  if (!TERMINAL.includes("{{ job.status }}")) setTimeout(poll, 3000);
</script>
```

- Convention: the HTML routes already return proper status codes — see
  `job_detail` in `app.py:110-120`, which renders `error.html` with
  `status_code=404`. The JSON route should be equally honest.
- `fastapi` is pinned `0.115.*` (`requirements.txt:1`); `HTTPException` is
  available from the `fastapi` package.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Tests (canonical, in Docker) | `docker compose run --rm web python -m pytest -q` | all pass, exit 0 |
| Manual check (stack up) | `curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/jobs/doesnotexist` | `404` |

## Scope

**In scope** (the only files you should modify):
- `autoclip/web/app.py`

**Out of scope** (do NOT touch, even though they look related):
- `autoclip/web/templates/job.html` — the `!res.ok` guard already handles a
  404 correctly (stops polling); it also has unrelated uncommitted edits you
  must not disturb.
- `job_detail` (HTML route) — already returns 404 correctly.
- Writing endpoint tests — plan `004-test-baseline-ci.md` adds the test
  harness and covers this endpoint; don't duplicate that scaffolding here.

## Git workflow

- Branch: `advisor/002-api-job-status-404`
- Single commit; message style matches repo history (imperative, no prefix),
  e.g. "Return 404 from job status API for missing jobs".
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Raise HTTPException for missing jobs

In `autoclip/web/app.py`:

1. Add `HTTPException` to the existing `fastapi` import on line 6.
2. Replace `return {"error": "not found"}` in `job_status` with
   `raise HTTPException(status_code=404, detail="job not found")`.

**Verify**: `docker compose run --rm web python -c "import autoclip.web.app"`
→ exit 0 (imports cleanly).

### Step 2: Confirm live behavior

Bring the stack up (`docker compose up -d --build`), then:

**Verify**: `curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/jobs/doesnotexist` → `404`
**Verify**: `curl -s http://localhost:8000/api/jobs/doesnotexist` → body contains `"job not found"`

(If the stack cannot be started in your environment, note that in your report
and rely on Step 1's import check plus the test suite.)

### Step 3: Run the test suite

**Verify**: `docker compose run --rm web python -m pytest -q` → all pass, exit 0.

## Test plan

Covered by plan 004 (adds the FastAPI TestClient harness and asserts this
endpoint returns 404 for unknown ids). No new tests in this plan.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `grep -n "error.*not found" autoclip/web/app.py` returns no matches
- [ ] `curl` check returns `404` (or Step 2 skip is documented in the report)
- [ ] `docker compose run --rm web python -m pytest -q` exits 0
- [ ] `git status` shows only `autoclip/web/app.py` (and `plans/README.md`)
      modified — the pre-existing template modifications excluded
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- `job_status` in `app.py` no longer matches the excerpt (drifted).
- The polling script in `job.html` no longer uses `if (!res.ok) return;` —
  the free-fix assumption is broken; the JS would then need its own change,
  which is out of scope here.
- Anything else in the codebase string-matches on the `{"error": "not found"}`
  payload (search first: `grep -rn '"error"' autoclip/`).

## Maintenance notes

- If a JS client is ever added that wants structured errors, FastAPI renders
  `HTTPException` as `{"detail": "job not found"}` — that shape is now part of
  the API surface.
- Reviewer: confirm no other endpoint returns soft errors with 200 (at
  planning time, `job_status` was the only one).

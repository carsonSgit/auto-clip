# Plan 003: Make canvas layouts survive portrait/square sources

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat 60ecfba..HEAD -- autoclip/render/ tests/`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED (changes render geometry; landscape-source output must stay
  pixel-identical — that is what the existing tests pin)
- **Depends on**: none
- **Category**: bug
- **Planned at**: commit `60ecfba`, 2026-06-11

## Why this matters

Two related defects in the render geometry, both confirmed by reading the code:

1. **Portrait sources overflow canvas formats.** `compute_layout` for canvas
   formats always sets `video_w = W` (full canvas width) and derives
   `video_h` from the source aspect ratio. For a portrait source (e.g.
   1080×1920 phone footage) on the `1x1` format (1080×1080):
   `video_h = 1080 × 1920/1080 = 1920 > 1080`, and
   `video_y = int((1080 − 1920) × 0.45) = −378`. The video is drawn at a
   negative offset, overflowing the canvas; the headline overlaps it and
   caption margins collapse to the minimum. The tool accepts phone footage
   (`.mp4`/`.mov` uploads) so this is reachable, not theoretical.

2. **Fragile landscape/canvas discriminator.** `build_render_command` decides
   which ffmpeg filter graph to build with
   `layout["video_y"] == 0 and layout["video_w"] == W`. Canvas layouts always
   have `video_w == W`, so the discriminator rests entirely on `video_y != 0`.
   A source whose aspect ratio matches the canvas format (e.g. a square
   source on `1x1`) yields `video_y == 0` and gets silently routed down the
   landscape branch: no branded background, wrong filter graph for the
   layout's intent.

The fix: carry an explicit `kind` field on the layout dict (the format
already declares it — `FORMATS[..]["layout"]`), and make canvas layouts
fit-to-frame instead of fit-to-width.

## Current state

- `autoclip/render/formats.py` — declares each format's `layout` as
  `"landscape"` or `"canvas"` (`16x9` is landscape; `9x16`, `1x1`, `4x5` are
  canvas). 1080×1920, 1080×1080, 1080×1350 respectively.
- `autoclip/render/layout.py` — `compute_layout(fmt, source_w, source_h,
  logo_w, logo_h, brand)`. Canvas branch, lines 33–49:

```python
    # Canvas: full-width video, vertically biased slightly above center.
    video_w = W
    video_h = _even(video_w * source_h / source_w)
    video_y = int((H - video_h) * 0.45)
    scaled_logo_w = _even(W * logo_frac)
    scaled_logo_h = int(scaled_logo_w * logo_h / max(logo_w, 1))
    bottom_band = H - (video_y + video_h)
    return {
        "W": W, "H": H,
        "video_w": video_w, "video_h": video_h, "video_y": video_y,
        "logo_w": scaled_logo_w,
        "logo_x": f"({W}-w)/2",
        "logo_y": str(margin),
        "sub_margin_v": max(40, int(bottom_band * 0.4)),
        "headline": bool(brand.get("headline", {}).get("enabled", True)),
        "headline_margin_v": margin + scaled_logo_h + 36,
    }
```

  The landscape branch (lines 20–31) returns a similar dict with
  `"video_w": W, "video_h": H, "video_y": 0` and `"headline": False`.
  `_even()` (lines 4–5) rounds to the nearest even int (libx264 needs even
  dimensions).

- `autoclip/render/ffmpeg_cmds.py` — `build_render_command`, lines 34–54.
  The discriminator and the canvas filter graph:

```python
    if layout["video_y"] == 0 and layout["video_w"] == W:  # landscape: video fills frame
        ...
    else:  # canvas: branded background, centered video, top logo
        bg = f"color=c=0x{canvas_bg_hex.lstrip('#')}:s={W}x{H}:r=30:d={duration:.3f}"
        cmd = base + ["-f", "lavfi", "-i", bg]
        filters = (
            f"[0:v]scale={layout['video_w']}:{layout['video_h']},setsar=1[vid];"
            f"[1:v]scale={layout['logo_w']}:-1[logo];"
            f"[2:v][vid]overlay=0:{layout['video_y']}[b1];"
            ...
```

  Note the hardcoded `overlay=0:` — horizontal centering doesn't exist yet
  because video was always full-width.

- `tests/test_ffmpeg_cmds.py` — existing tests; all build layouts from a
  **1920×1080 source** via the `_cmd` helper (line 9:
  `compute_layout(FORMATS[fmt_name], 1920, 1080, 720, 200, brand)`), and
  `test_canvas_command_has_branded_background` asserts
  `f"overlay=0:{layout['video_y']}"` — that assertion must be updated to the
  new x-expression. The `brand` fixture lives in `tests/conftest.py`.
- Conventions: pure-function modules under `autoclip/render/`, plain pytest
  functions, fixtures from `conftest.py`, no mocking. Match
  `tests/test_ffmpeg_cmds.py` style.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Tests (canonical, in Docker) | `docker compose run --rm web python -m pytest -q` | all pass, exit 0 |
| Targeted tests | `docker compose run --rm web python -m pytest tests/test_ffmpeg_cmds.py tests/test_layout.py -q` | all pass |

These modules are dependency-light; on a host venv `pip install pytest` plus
the repo on `PYTHONPATH` also runs them (`python -m pytest tests/test_ffmpeg_cmds.py -q`).

## Scope

**In scope** (the only files you should modify):
- `autoclip/render/layout.py`
- `autoclip/render/ffmpeg_cmds.py`
- `tests/test_ffmpeg_cmds.py` (update the one assertion noted above)
- `tests/test_layout.py` (create)

**Out of scope** (do NOT touch, even though they look related):
- `autoclip/render/render.py` — passes layout dicts through untouched; adding
  a key is backward-compatible.
- `autoclip/render/subtitles.py` and `formats.py` — caption timing and format
  definitions are unrelated.
- The landscape branch's filter graph in `ffmpeg_cmds.py` — only the *branch
  condition* changes, not the landscape filters; landscape output must stay
  byte-identical.

## Git workflow

- Branch: `advisor/003-canvas-layout-aspect`
- One commit per step or one combined commit; message style matches repo
  history (imperative, no prefix), e.g. "Fit canvas video to frame and branch
  renders on explicit layout kind".
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Add explicit `kind` to both layout dicts

In `autoclip/render/layout.py`, add `"kind": "landscape"` to the landscape
return dict and `"kind": "canvas"` to the canvas return dict (first key, for
readability).

**Verify**: `python -m pytest tests/test_ffmpeg_cmds.py -q` (host or Docker)
→ still all pass (nothing reads the key yet).

### Step 2: Branch `build_render_command` on `layout["kind"]`

In `autoclip/render/ffmpeg_cmds.py` replace
`if layout["video_y"] == 0 and layout["video_w"] == W:` with
`if layout["kind"] == "landscape":`. Keep the comment.

**Verify**: `python -m pytest tests/test_ffmpeg_cmds.py -q` → all pass
(existing 1920×1080-source cases route identically).

### Step 3: Fit-to-frame in the canvas branch of `compute_layout`

Replace the first three lines of the canvas branch so the video scales to fit
*within* W×H instead of always filling the width, and add a horizontal
offset:

```python
    # Canvas: video fit within the frame (full-width for landscape sources,
    # full-height for portrait), vertically biased slightly above center.
    video_w = W
    video_h = _even(video_w * source_h / source_w)
    if video_h > H:  # portrait/tall source: fit height instead
        video_h = H
        video_w = _even(video_h * source_w / source_h)
    video_x = (W - video_w) // 2
    video_y = max(0, int((H - video_h) * 0.45))
```

Add `"video_x": video_x,` to the returned dict (next to `video_y`). Also add
`"video_x": 0,` to the **landscape** dict so the key always exists.
`bottom_band` stays as written — with the clamp it is now always ≥ 0.

**Verify**: `python -c "from autoclip.render.layout import compute_layout; from autoclip.render.formats import FORMATS; l = compute_layout(FORMATS['1x1'], 1080, 1920, 720, 200, {'logo': {}, 'headline': {}}); print(l['video_w'], l['video_h'], l['video_x'], l['video_y'])"`
→ `608 1080 236 0` (video fits the 1080×1080 canvas, centered horizontally).

### Step 4: Use `video_x` in the canvas filter graph

In `ffmpeg_cmds.py`'s canvas branch, change
`f"[2:v][vid]overlay=0:{layout['video_y']}[b1];"` to
`f"[2:v][vid]overlay={layout['video_x']}:{layout['video_y']}[b1];"`.

In `tests/test_ffmpeg_cmds.py`, update the assertion in
`test_canvas_command_has_branded_background` from
`f"overlay=0:{layout['video_y']}"` to
`f"overlay={layout['video_x']}:{layout['video_y']}"` (for the existing
landscape source `video_x` is 0, so the rendered string is unchanged).

**Verify**: `python -m pytest tests/test_ffmpeg_cmds.py -q` → all pass.

### Step 5: New tests in `tests/test_layout.py`

Create `tests/test_layout.py`, modeled on `tests/test_ffmpeg_cmds.py` (plain
functions, `brand` fixture from conftest). Cases to cover (use logo 720×200):

1. **Portrait source on 1x1 canvas** — `compute_layout(FORMATS["1x1"], 1080, 1920, ...)`:
   assert `video_h <= 1080`, `video_y >= 0`, `video_x > 0`,
   `video_x + video_w <= 1080`, and `video_w % 2 == 0`.
2. **Portrait source on 9x16 canvas** — source 1080×1920 on 1080×1920: video
   fills the frame (`video_w == 1080`, `video_h == 1920`, `video_x == 0`,
   `video_y == 0`).
3. **Square source on 1x1 routes to canvas branch** — build the command via
   `build_render_command` with a layout from a 1080×1080 source on `1x1`;
   assert `"color=" in " ".join(cmd)` (lavfi background present — this is the
   regression test for the old discriminator bug).
4. **Landscape source unchanged** — `compute_layout(FORMATS["9x16"], 1920, 1080, ...)`
   still yields `video_w == 1080`, `video_h == 608`, `video_x == 0` (pins
   that the mainline path didn't move).
5. **kind field** — `16x9` layout has `kind == "landscape"`, the other three
   have `kind == "canvas"`.

**Verify**: `python -m pytest tests/test_layout.py -q` → all new tests pass.

### Step 6: Full suite + optional render smoke

**Verify**: `docker compose run --rm web python -m pytest -q` → all pass.

Optional (only if the stack and a sample video are available): upload a
portrait phone clip through the UI and eyeball `clip_0/1x1.mp4` — video
centered on the branded background, nothing cropped at the frame edge.

## Test plan

See Step 5 — five new cases in `tests/test_layout.py` plus one updated
assertion in `tests/test_ffmpeg_cmds.py`. Pattern file:
`tests/test_ffmpeg_cmds.py`.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `grep -n "video_y\"\] == 0" autoclip/render/ffmpeg_cmds.py` returns no matches
- [ ] `grep -n "\"kind\"" autoclip/render/layout.py` shows 2 matches
- [ ] `docker compose run --rm web python -m pytest -q` exits 0 with ≥18 tests
      (13 existing + 5 new)
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- The canvas branch in `layout.py` or the discriminator in `ffmpeg_cmds.py`
  no longer matches the excerpts (drifted — possibly already fixed).
- Existing tests fail after Step 2 (means some layout reaches
  `build_render_command` without going through `compute_layout` — find out
  who, report, don't patch around it).
- You find a third consumer of `layout["video_y"]`/`video_w` outside the two
  in-scope modules (`grep -rn "video_y" autoclip/`) — the key contract is
  wider than this plan assumed.

## Maintenance notes

- A future "smart crop / face tracking" feature (typical for this tool
  category) replaces this fit-to-frame logic entirely; until then, `kind` is
  the single switch for filter-graph selection — keep it authoritative.
- For full-bleed canvas cases (portrait on 9x16) the headline now renders on
  top of video rather than on background band — acceptable, social-native
  look; reviewer should be aware it's intentional.
- Reviewer should diff the generated ffmpeg command for a 1920×1080 source
  before/after: it must be identical except for the (string-equal) overlay
  expression.

# Deploying auto-clip to Railway

auto-clip is a CPU-heavy, multi-service Docker app (FastAPI web + Celery worker +
Redis + Postgres) that moves media files between the web and worker through a shared
`/data` directory. Railway Volumes attach to a **single** service, and the design
rules out object storage, so the web server and worker run **together in one Railway
service** backed by one Volume. `railway.json` and `scripts/railway_start.sh` in this
repo encode that.

## One-time setup

1. **Create the project from GitHub**
   Railway → *New Project* → *Deploy from GitHub repo* → select `carsonSgit/auto-clip`.
   Railway reads `railway.json` and builds `docker/Dockerfile`. Rename the service to
   `app` if you like.

2. **Add Postgres**
   *New* → *Database* → *Add PostgreSQL*.

3. **Add Redis**
   *New* → *Database* → *Add Redis*.

4. **Attach a Volume to the `app` service**
   Right-click the `app` service → *Attach Volume* → mount path **`/data`**.
   (Uploads, scratch work, outputs, and the Whisper model cache all live here.)

5. **Set the `app` service variables** (Variables tab):

   | Variable | Value | Notes |
   |---|---|---|
   | `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` | reference variable |
   | `REDIS_URL` | `${{Redis.REDIS_URL}}` | reference variable |
   | `OUTPUT_DIR` | `/data/outputs` | keeps outputs on the Volume |
   | `HF_HOME` | `/data/hf-cache` | persists the ~460 MB Whisper model across restarts |
   | `ANTHROPIC_API_KEY` | *(optional)* | enables LLM highlights; omit for heuristic mode |
   | `WHISPER_MODEL` | `small` | `tiny`/`base`/`small`/`medium` (bigger = slower on CPU) |
   | `MAX_UPLOAD_MB` | `2048` | reject larger uploads |
   | `CELERY_CONCURRENCY` | `1` | parallel jobs; raise only with more vCPU |

   `DATA_DIR` defaults to `/data` and `BRANDKIT_DIR` to `/app/brandkit`; no need to set them.

6. **Enable a public domain**
   `app` service → *Settings* → *Networking* → *Generate Domain*. Railway routes it to
   the port the app binds (`$PORT`, handled by the start script). The healthcheck uses
   `/healthz`.

7. **Deploy.** First boot downloads the Whisper model into `/data/hf-cache` (one-time).

## Resources

The `small` int8 model needs roughly 2 GB RAM; transcription + rendering are CPU-bound
and run for minutes per job. Give the `app` service enough vCPU/RAM on your plan, and
scale `CELERY_CONCURRENCY` only alongside vCPU.

## Branding

Replace `brandkit/brand.yaml` + `brandkit/assets/` with real branding and redeploy —
no code changes needed.

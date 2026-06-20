#!/usr/bin/env bash
# Start the web server and the Celery worker together in one Railway service.
#
# Railway gives each service its own ephemeral filesystem and a Volume can attach
# to only ONE service, but auto-clip passes media between the web and worker via a
# shared /data + /outputs directory (the design rules out S3/object storage). So we
# run both processes in a single service backed by one Volume mounted at /data.
set -euo pipefail

concurrency="${CELERY_CONCURRENCY:-1}"
port="${PORT:-8000}"

echo "Starting Celery worker (concurrency=${concurrency})..."
celery -A autoclip.pipeline.celery_app worker --loglevel=info --concurrency="${concurrency}" &
worker_pid=$!

echo "Starting web server on port ${port}..."
uvicorn autoclip.web.app:app --host 0.0.0.0 --port "${port}" &
web_pid=$!

# If either process dies, take the whole service down so Railway restarts it.
trap 'kill "${worker_pid}" "${web_pid}" 2>/dev/null || true' TERM INT
wait -n
status=$?
echo "A process exited (status ${status}); shutting the service down."
kill "${worker_pid}" "${web_pid}" 2>/dev/null || true
exit "${status}"

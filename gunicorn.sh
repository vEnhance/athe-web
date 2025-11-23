#!/usr/bin/env bash

set -euo pipefail
umask 002

reload() {
    uv sync --all-extras --no-dev
    uv run --no-sync python3 manage.py migrate
    kill -HUP "$GUNICORN_PID"
}

trap reload HUP

# Initial sync and migrate
uv sync --all-extras --no-dev
uv run --no-sync python3 manage.py migrate

# Start gunicorn in background
uv run --no-sync gunicorn atheweb.wsgi &
GUNICORN_PID=$!

# Wait for gunicorn, restarting wait after signals
while kill -0 "$GUNICORN_PID" 2>/dev/null; do
    wait "$GUNICORN_PID" || true
done

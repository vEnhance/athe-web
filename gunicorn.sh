#!/usr/bin/env bash

set -euo pipefail
umask 002

reload() {
  uv run --no-sync python3 manage.py migrate
  kill -HUP "$GUNICORN_PID"
}

trap reload HUP

# We do NOT run uv sync as web user (will cause perm issues)
# That should be handled by the git post-receive hook

# Initial migrate
uv run --no-sync python3 manage.py migrate

# Start gunicorn in background
uv run --no-sync gunicorn atheweb.wsgi &
GUNICORN_PID=$!

# Wait for gunicorn, restarting wait after signals
while kill -0 "$GUNICORN_PID" 2>/dev/null; do
  wait "$GUNICORN_PID" || true
done

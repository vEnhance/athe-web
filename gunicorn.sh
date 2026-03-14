#!/usr/bin/env bash

set -euo pipefail
umask 002

log() {
  echo "[$(date +"%F %T %Z")] $1"
}

reload() {
  log "♻️ RELOAD TRIGGERED. Every day I'm shuffling 🔀"
  uv run --no-sync python3 manage.py migrate
  kill -HUP "$GUNICORN_PID"
}

trap reload HUP

# We do NOT run uv sync as web user (will cause perm issues)
# That should be handled by the git post-receive hook

log "☀️  GOOD MORNING, my glorious webmaster! How are you this fine $(date +"%A in %B")?"
log "🩷 Please enjoy these logs, I wrote them just for you 💌🖋️"

# Initial migrate
uv run --no-sync python3 manage.py migrate

# Start gunicorn in background
uv run --no-sync gunicorn atheweb.wsgi &
GUNICORN_PID=$!

# Wait for gunicorn, restarting wait after signals
while kill -0 "$GUNICORN_PID" 2>/dev/null; do
  wait "$GUNICORN_PID" || true
done

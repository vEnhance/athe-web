#!/usr/bin/env bash
set -euo pipefail

uv sync
uv run python3 manage.py migrate
uv run gunicorn atheweb.wsgi

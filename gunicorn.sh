#!/usr/bin/env bash

set -euo pipefail
umask 002

uv sync --all-extras --no-dev
uv run python3 manage.py migrate
uv run gunicorn atheweb.wsgi

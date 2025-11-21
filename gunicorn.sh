#!/usr/bin/env bash

set -euo pipefail
umask 002

uv sync --group prod
uv run python3 manage.py migrate
uv run gunicorn atheweb.wsgi

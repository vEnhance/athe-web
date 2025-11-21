#!/usr/bin/env bash

set -euo pipefail
umask 002

uv sync --all-extras --no-dev
uv run --no-dev python3 manage.py migrate
uv run --no-dev gunicorn atheweb.wsgi

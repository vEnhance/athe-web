#!/usr/bin/env bash

set -euo pipefail
umask 002

uv sync --all-extras --no-dev
uv run --no-sync python3 manage.py migrate
uv run --no-sync gunicorn atheweb.wsgi

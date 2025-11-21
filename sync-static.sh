#!/usr/bin/env bash
set -euo pipefail

uv run python manage.py collectstatic --no-input
rsync -r static/ atheweb:/home/public/static/

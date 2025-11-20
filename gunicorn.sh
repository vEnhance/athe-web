#!/usr/bin/env bash
set -euo pipefail

uv run gunicorn atheweb.wsgi

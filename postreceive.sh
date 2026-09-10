#!/bin/bash

# Post-receive hook designed specifically for the NearlyFreeSpeech prod server

set -euo pipefail

export OPENSSL_DIR=/usr   # see NFS.md
export CARGO_BUILD_JOBS=1 # see NFS.md

TARGET=/home/protected/atheweb/
mkdir -p "$TARGET"
cd "$TARGET" || exit 1

git --git-dir="/home/private/atheweb.git" --work-tree="." checkout -f main
uv sync --all-extras --no-dev
uv run --all-extras --no-dev python manage.py collectstatic --no-input

nfsn signal-daemon django hup

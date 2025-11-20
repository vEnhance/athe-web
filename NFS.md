# Notes for NearlyFreeSpeech setup

The part where you plug in all the wires and pray.

- Create a site
- Create an SQL
- Add an `.env` file (for Evan this is `athemath.env`)
- Install `uv` (struggle bus)
- Create a bare repository `~/atheweb.git`
- Here's a wrapper script to use as a git post-receive hook

```bash
#!/bin/bash

set -euo pipefail

TARGET=/home/protected/atheweb/
mkdir -p "$TARGET"
chown atheweb:web "$TARGET"
chmod g+s "$TARGET"
cd "$TARGET" || exit
git --git-dir="/home/private/atheweb.git" --work-tree="." checkout -f main
```

- Make sure permissions work in `public` and `protected`:
  - `chgrp` all relevant folders to `web`
  - `chmod g+s` everything (`static/`, `/media`, and the repository).
  - Make sure `web` is the group for both `static/` and `media` too
  - Write a simple `.htaccess` that says `Require all granted` for `/home/public`

- Create a daemon using `gunicorn.sh`
- Set up proxies for `static/` and `media/`

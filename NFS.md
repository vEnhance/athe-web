# Notes for NearlyFreeSpeech setup

## Setup

The part where you plug in all the wires and pray.

- Create a site
- Create an SQL
- Add an `.env` file (for Evan this is `athemath.env`)
- Install `uv` (struggle bus)
- Create a bare repository `~/atheweb.git`
- Here's a script to use as a git post-receive hook

```bash
#!/bin/bash

set -euo pipefail

TARGET=/home/protected/atheweb/
mkdir -p "$TARGET"
cd "$TARGET" || exit 1
git --git-dir="/home/private/atheweb.git" --work-tree="." checkout -f main
chgrp -R web .
nfsn signal-daemon django hup
```

- Make sure permissions work in `public` and `protected`:
  - `chgrp` and `chmod g+s` all of `static/`, `/media`, and the repository
  - Write a simple `.htaccess` that says `Require all granted` for `/home/public`

- Create a daemon using `gunicorn.sh`
- Set up proxies for `static/` and `media/`

- Apparently you have to install time zones manually,
  [as described here](https://members.nearlyfreespeech.net/forums/viewtopic.php?t=11631).

  `mysql -h $HOST -u venhance -p mysql <timezones.sql`

  Then `flush tables;` to actually get it live.

## Gotchas: permission issues

- When running commands, be careful to use `uv run --no-sync`
  to avoid writing to the virtualenv.
- The daemon runs as a user `web` and not the main user `atheweb`.
  So if the main writes to the virtual environment,
  permission errors will arise later on.
- If that does happen, `chgrp -R web`.

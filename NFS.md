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

export OPENSSL_DIR=/usr
export CARGO_BUILD_JOBS=1
TARGET=/home/protected/atheweb/
mkdir -p "$TARGET"
cd "$TARGET" || exit 1
git --git-dir="/home/private/atheweb.git" --work-tree="." checkout -f main
uv sync --all-extras --no-dev
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

## Gotcha: OpenSSL

FreeBSD might pick up an ancient version of OpenSSL (like 1.x)
which will cause `cryptography` build with `maturin` to fail.
That's why we have `export OPENSSL_DIR=/usr` above.

## Gotcha: nh3 and other Rust extensions

`nh3` (pulled in by `django-markdownfield`) publishes wheels for Linux, macOS and
Windows only, so on FreeBSD `uv sync` always compiles it from source with cargo.
Cargo defaults to one build job per core, and several of the crates in that tree
(`icu_properties_data`, `syn`) are memory-hungry, so the parallel `rustc` processes
blow past the jail's per-process memory cap and get SIGKILLed:

```text
error: could not compile `syn` (lib)
  process didn't exit successfully: `rustc ...` (signal: 9, SIGKILL: kill)
```

That's why we have `export CARGO_BUILD_JOBS=1` above. The build takes a few minutes
but only happens once per `nh3` version: uv caches the wheel it produces, so later
deploys reuse it. If a deploy fails this way after a dependency bump, run
`CARGO_BUILD_JOBS=1 uv sync --all-extras --no-dev` by hand as the `atheweb` user to
warm the cache, then re-run the hook. Don't `uv cache clean`; it throws away the
built wheels.

## Gotchas: permission issues on protected/

- On NFS, the main user `atheweb` and the more restricted `web` user (daemon)
  will often fight for ownership of the `.venv` directory.
- My strategy right now is to have only the `atheweb` user
  do any `uv` operations.
- Thus, web scripts will always run `uv run --no-sync`
  to avoid writing to the virtualenv.

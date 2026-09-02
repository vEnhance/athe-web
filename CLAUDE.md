# Development Notes

Notes and decisions for the athe-web project. See [README.md](README.md) for first-time
setup, [OAUTH_SETUP.md](OAUTH_SETUP.md) for OAuth credentials, and [NFS.md](NFS.md) for
deployment.

## Project Setup

This is a Django web application (not a library/package), managed with **uv**. There is
deliberately no `[build-system]` in `pyproject.toml` — we are not building a package.

Python 3.14+ is required (`.python-version`, `requires-python`). The database is SQLite in
development and MySQL in production.

## Development Workflow

Run `make help` to see all available commands:

- `make install` - `uv sync` plus `prek install` to set up the git hooks
- `make runserver` - Development server (`runserver_plus`)
- `make migrate` / `make migrations` - Apply / create migrations
- `make fmt` - Run every prek hook over all files
- `make check` - Django checks, template validation, missing-migration check, pyright
- `make test` - `pytest -n auto`
- `make ci` - fmt + check + test

`make migrations` pipes the new migration files back through prek, so generated migrations
land already formatted.

Anything not covered by a target is `uv run python manage.py <command>`. Use
`uv run python manage.py shell_plus` for a shell with models auto-imported.

## Apps

Local apps in `INSTALLED_APPS`:

| App             | Purpose                                                                                           |
| --------------- | ------------------------------------------------------------------------------------------------- |
| `atheweb`       | Project package: settings, urls, and the views/decorators/validators that belong to no single app |
| `courses`       | Semesters, courses, clubs, meetings, students, global events, calendar tokens                     |
| `dashboard`     | The logged-in landing page; owns no models, reads from the apps that do                           |
| `home`          | Public splash page, staff photo listings, pset application forms                                  |
| `housepoints`   | House point awards and Discord house updates                                                      |
| `misc`          | One-off static pages                                                                              |
| `reg`           | Registration wizard, invite links, course preferences                                             |
| `ta_attendance` | Staff attendance records for club sessions                                                        |
| `weblog`        | Blog posts, with custom markdown extensions                                                       |
| `yearbook`      | Student yearbook entries                                                                          |

`courses.models` imports `home.models`, so anything that needs both belongs above them
(`dashboard` or `atheweb`) rather than inside either.

## Dependencies

Production dependencies live in `dependencies` in `pyproject.toml`, with the extra
production-only server bits (gunicorn, mysqlclient) under `[project.optional-dependencies]`
as the `prod` extra. Development dependencies are in `[dependency-groups]` under `dev`.
After editing either, run `uv lock` and then `make install`.

The linters and formatters (**ruff**, **djlint**, **codespell**, **prettier**, **rumdl**,
**zizmor**, **shellcheck**, **shfmt**) are deliberately *not* dev dependencies. prek pins
their versions in `prek.toml` and runs them in its own isolated environments, so listing
them in `pyproject.toml` too would just drift out of sync. Run them via `make fmt`, not
`uv run`. Their configuration still lives in `pyproject.toml` (`[tool.ruff]`,
`[tool.djlint]`, `[tool.codespell]`) and `rumdl.toml`, which the hooks read.

## Code Quality

### Type Checking

pyright in basic mode, configured in `pyproject.toml`. Migrations, tests, and `apps.py` are
excluded. Add type hints to new code and run `make check` to verify.

### Linting and Formatting

ruff handles both linting and formatting:

- Line length: 88 characters
- Migrations and `manage.py` excluded from linting
- `RUF012` ignored project-wide (Django class attributes are mutable by design)
- Special rules for `settings.py` and test files

### Testing

`make test` (or `uv run pytest`). pytest is configured via `[tool.pytest.ini_options]` in
`pyproject.toml`. Most apps keep a `tests/` package of `test_*.py` files; shared fixtures
live in the root `conftest.py`.

## Git Hooks

Hooks are configured in `prek.toml` and installed by `make install`. They run at three
stages:

- **pre-commit**: JSON/TOML/YAML validation, merge conflict and private key checks,
  whitespace and EOF fixers, ruff format/lint, djlint, prettier, rumdl, codespell, zizmor,
  shellcheck, shfmt, `uv lock`
- **commit-msg**: conventional commit message format
- **pre-push**: `make fmt`, `make check`, `make test`

Commit messages must start with one of the types listed in `prek.toml`; alongside the
conventional ones we also use `drop`, `edit`, `polish`, `root`, and `temp`.

## CI/CD

`.github/workflows/ci.yml` runs on push/PR to main and does `make fmt`, `make check`, then
`make test`.

## Deployment

Deployed to NearlyFreeSpeech; see [NFS.md](NFS.md).

- `deploy.sh` - Pushes main to the `production` remote (refuses unless local main matches
  origin/main)
- `gunicorn.sh` - Production entry point: migrates, starts gunicorn, re-migrates and
  reloads workers on SIGHUP
- `sync-static.sh` - `collectstatic` plus rsync to the production static directory
- `run-discord-remind.sh` / `run-discord-house.sh` - Cron entry points for the
  `send_discord_reminders` and `send_discord_house_updates` management commands

## Authentication

Google, GitHub, and Discord OAuth are the primary methods and are emphasized in the UI;
username/password is a de-emphasized fallback. Admins can impersonate users through
django-hijack.

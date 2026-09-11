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
live in the root `conftest.py`, and an app may add its own `tests/conftest.py` for
fixtures only it wants.

The `athe` fixture is a Django test client that knows who is logged in, wrapped by
`AtheClient` in [atheweb/testsuite.py](atheweb/testsuite.py): `athe.login(user_or_username)`
plus `get_ok`, `post_ok`, `get_redirects` and `post_redirects`, which assert the status
so a test does not have to. The `make_user`, `make_semester`,
`make_student`, `make_course` and `make_staff_listing` fixtures build the rows every
app needs; anything created through `make_user` has the password `athe.login` expects.
[dashboard/tests/test_dashboard.py](dashboard/tests/test_dashboard.py) is the worked
example.

#### What to assert on

Do not assert on rendered template prose. Rewording a message should never break a
test, and a bare substring search over the page is weak as well as brittle:
`assert "5" in content` matches the 5 inside 15. Reach for these in order:

1. **`response.context[...]`** — for what the view computed. These views already put
   the interesting values there (`dash_classes`, `leaderboard_data`, `grand_total`,
   `notice`, `form`), so assert on those directly.
2. **A direct database read** — for what a POST actually wrote. Assert on the model,
   not on the confirmation page rendered afterwards.
3. **`athe.assert_testid(resp, "...")`** — for whether an element is visible to this
   user, and `assert_testid_count` for how many there are. Add a `data-testid`
   attribute to the template and assert on that, never on the surrounding wording or
   Bootstrap classes. Add one only where a test needs it.
4. **`athe.text_of(resp, "...")`** — for a value the page prints that is not in the
   context, such as a house tile's total. It returns the visible text inside that one
   element, whitespace collapsed; `texts_of` returns every match, in document order,
   which is how to check ordering. Scoping to an element is what keeps this honest.

Searching `response.content` is for the two cases where the bytes really are the
contract:

- **Leakage checks** — asserting content is *absent* from a page someone may not see.
- **Attributes another program reads** — `loading="lazy"`, the `data-semester-end` that
  `manage_meetings.js` reads, an `href` a test is checking points somewhere.

Asserting on `messages` text is fine when the string is a fixed literal — it lives in
`views.py` next to the code you are editing, so a reword breaks one obvious test. Do
**not** assert on a message that interpolates a value; that couples the test to a
model's `__str__`. Assert the state change instead, plus the level if it matters that
the user was notified:

```python
assert any(m.level == message_levels.SUCCESS for m in resp.context["messages"])
```

Import it as `from django.contrib.messages import constants as message_levels` —
`messages` is already a common local variable name in these files.

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

## Pull Requests

Open pull requests with a title only — no description body. Descriptions get rewritten by
hand anyway, so anything generated is wasted effort.

## CI/CD

`.github/workflows/ci.yml` runs on push/PR to main and does `make fmt`, `make check`, then
`make test`.

## Deployment

Deployed to NearlyFreeSpeech; see [NFS.md](NFS.md).

- `deploy.sh` - Pushes main to the `production` remote (refuses unless local main matches
  origin/main)
- `gunicorn.sh` - Production entry point: migrates, starts gunicorn, re-migrates and
  reloads workers on SIGHUP
- `run-discord-remind.sh` / `run-discord-house.sh` - Cron entry points for the
  `send_discord_reminders` and `send_discord_house_updates` management commands

Uploaded images are re-encoded down to the size they display at, by
`DownscaledImageField` (`atheweb/fields.py`) via the helpers in `atheweb/images.py`. Staff
photos become 512px JPEGs, since they never render larger than 200px. Weblog photos get a
2048px cap and keep their format and file name, because their URLs are pasted into post
markdown and one is hardcoded in `virtual_program.html`; formats we cannot re-encode without
renaming, such as animated GIFs, are left alone.

`shrink_photos` is a one-time backfill for images uploaded before that. It rewrites files
under `MEDIA_ROOT` and nothing backs `media/` up, so tar up `photos/` and `staff_photos/`
first and run `--dry-run` before the real thing. Either mode ends with a breakdown counting
every stored image by outcome, which doubles as a survey of what is in `media/` — including
rows whose file has gone missing.

## Authentication

Google, GitHub, and Discord OAuth are the primary methods and are emphasized in the UI;
username/password is a de-emphasized fallback. Admins can impersonate users through
django-hijack.

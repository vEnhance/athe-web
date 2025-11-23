# Development Notes

This document contains development notes and decisions for the athe-web project.

## Project Setup

This is a Django web application (not a library/package), managed with **uv** for dependency management.

## Development Workflow

### Quick Start

```bash
# Install dependencies
make install
# Run migrations
make migrate
# Start development server
make runserver
```

### Common Commands

Run `make help` to see all available commands:

- `make install` - Install dependencies with uv and set up pre-commit hooks
- `make runserver` - Run Django development server (runserver_plus)
- `make migrate` - Apply database migrations
- `make migrations` - Create new migrations
- `make fmt` - Run code formatters and linters (via prek)
- `make check` - Run Django checks, template validation, migration check, and type checking
- `make test` - Run tests with pytest (parallel execution)
- `make ci` - Run fmt + check + test

You can also use `uv run python manage.py <command>` directly for any Django command.

## Dependencies

### Production Dependencies

- **Django 5.2**: Web framework
- **django-allauth**: Social authentication (Google, GitHub, Discord OAuth)
- **django-bootstrap5**: Bootstrap integration
- **django-extensions**: Useful Django extensions
- **django-hijack**: User impersonation for admins
- **django-markdownfield**: Markdown support for model fields
- **pillow**: Image processing
- **requests**: HTTP library
- **dotenv**: Environment variable management
- **ipython**: Enhanced Python shell
- **gunicorn**: Production WSGI server (prod extra)
- **mysqlclient**: MySQL database adapter (prod extra)

### Development Dependencies

- **ruff**: Fast Python linter and formatter
- **djlint**: Django template linter
- **pytest** + **pytest-django** + **pytest-xdist**: Testing framework with parallel support
- **pyright**: Static type checker
- **django-stubs**: Type stubs for Django
- **werkzeug**: WSGI utilities (for runserver_plus)
- **prek**: Pre-commit helper utilities

## Code Quality

### Type Checking

We use pyright with basic type checking configured in `pyproject.toml`. Migrations, tests, and `apps.py` are excluded.

### Linting and Formatting

We use ruff for both linting and formatting:

- Line length: 88 characters
- Migrations and `manage.py` excluded from linting
- Special rules for `settings.py` and test files

### Testing

Run `make test` or `uv run pytest`. Tests use pytest-django and are configured via `pytest.ini`.

## CI/CD

GitHub Actions workflow (`.github/workflows/ci.yml`) runs on push/PR to main:

1. `make fmt` - Formatting and linting
2. `make check` - Django checks, template validation, migration check, type checking
3. `make test` - Test suite (pytest)

## Project Structure

```
athe-web/
├── atheweb/          # Main Django project
├── courses/          # Courses app
├── home/             # Home page app
├── housepoints/      # House points tracking app
├── reg/              # Registration app
├── weblog/           # Blog/weblog app
├── fixtures/         # Database fixtures
├── .github/          # GitHub Actions CI
├── manage.py         # Django management script
├── pyproject.toml    # Project metadata and dependencies
├── uv.lock           # Locked dependencies
├── Makefile          # Development commands
├── pytest.ini        # Pytest configuration
├── .pre-commit-config.yaml  # Pre-commit hook configuration
├── gunicorn.sh       # Production server startup script
├── sync-static.sh    # Static files sync script
├── OAUTH_SETUP.md    # OAuth authentication setup guide
└── NFS.md            # NearlyFreeSpeech deployment notes
```

## Authentication

The application supports multiple authentication methods:

- **Google OAuth** (primary method, emphasized in UI)
- **GitHub OAuth** (primary method, emphasized in UI)
- **Discord OAuth** (primary method, emphasized in UI)
- **Username/Password** (fallback method, de-emphasized in UI)

For OAuth setup instructions, see [OAUTH_SETUP.md](OAUTH_SETUP.md).

## Tips for Development

1. **Always use `uv run`** for running Python commands to ensure you're using the project's virtual environment.
2. **Update dependencies**:

- Add to `dependencies` in `pyproject.toml` for production deps
- Add to `dev` in `[project.optional-dependencies]` for dev deps
- Run `uv lock` to update the lockfile
- Run `make install` to install

3. **Type hints**: Add type hints to new code. Run `make check` to verify types.
4. **Before committing**: Run `make ci` (or `make fmt`, `make check`, and `make test` individually) to verify everything works.
5. **Django shell**: Use `uv run python manage.py shell_plus` (from django-extensions) for an enhanced shell with models auto-imported.

## Pre-commit Hooks

Pre-commit hooks are configured in `.pre-commit-config.yaml`. They are installed automatically by `make install`.

Hooks run at different stages:

- **pre-commit**: JSON/YAML/TOML validation, merge conflict check, trailing whitespace, end-of-file fixer, ruff format/lint, djlint, prettier, codespell
- **commit-msg**: Conventional commit message format enforcement
- **pre-push**: `make fmt`, `make check`, `make test`

## Deployment

The application is deployed to NearlyFreeSpeech. See [NFS.md](NFS.md) for deployment details.

### Deployment Scripts

- `gunicorn.sh` - Starts the production server (syncs deps, runs migrations, starts gunicorn)
- `run-discord.sh` - Runs the Discord reminder management command
- `sync-static.sh` - Collects static files and syncs them to the production server

## Notes

- Python 3.11+ required (specified in `pyproject.toml`)
- Database: SQLite (development), MySQL (production)
- No `[build-system]` in pyproject.toml - this is intentional as we're not building a package

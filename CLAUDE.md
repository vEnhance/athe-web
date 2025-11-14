# Development Notes
This document contains development notes and decisions for the athe-web project.
## Project Setup
This is a Django web application (not a library/package), managed with **uv** for dependency management.
## Development Workflow
### Quick Start
```bash
# Install dependencies
make install
# or: uv sync --all-extras
# Run migrations
make migrate
# Create superuser
make createsuperuser
# Start development server
make runserver
```
### Common Commands
Run `make help` to see all available commands:
- `make install` - Install dependencies with uv
- `make runserver` - Run Django development server
- `make migrate` - Apply database migrations
- `make makemigrations` - Create new migrations
- `make createsuperuser` - Create a Django superuser
- `make check` - Run Django checks and type checking
- `make test` - Run tests
- `make fmt` - Run code formatter
You can also use `uv run python manage.py
<command>
` directly for any Django command.
## Dependencies
### Production Dependencies
- **Django 5.2**: Web framework
- **django-bootstrap5**: Bootstrap integration
- **django-extensions**: Useful Django extensions
- **ipython**: Enhanced Python shell
### Development Dependencies
- **ruff**: Fast Python linter and formatter
- **djlint**: Django template linter
- **pytest** + **pytest-django**: Testing framework
- **pyright**: Static type checker
- **django-stubs**: Type stubs for Django
## Code Quality
### Type Checking
We use pyright with strict settings configured in `pyproject.toml`. Migrations, tests, and `apps.py` are excluded.
### Linting and Formatting
We use ruff for both linting and formatting:
- Line length: 88 characters
- Migrations and `manage.py` excluded from linting
- Special rules for `settings.py` and test files
### Testing
Run `make test` or `uv run pytest`. Tests use pytest-django and are configured via `pytest.ini`.
## CI/CD
GitHub Actions workflow (`.github/workflows/ci.yml`) runs on push/PR to main:
1. Format check (`ruff format --check`)
2. Linting (`ruff check`)
3. Django checks + type checking (pyright)
4. Test suite (pytest)
## Project Structure
```
athe-web/
├── atheweb/          # Main Django project
├── courses/          # Courses app
├── fixtures/         # Database fixtures
├── .github/          # GitHub Actions CI
├── manage.py         # Django management script
├── pyproject.toml    # Project metadata and dependencies
├── uv.lock           # Locked dependencies
├── Makefile          # Development commands
└── pytest.ini        # Pytest configuration
```
## Tips for Development
1. **Always use `uv run`** for running Python commands to ensure you're using the project's virtual environment.
2. **Update dependencies**:
- Add to `dependencies` in `pyproject.toml` for production deps
- Add to `dev` in `[project.optional-dependencies]` for dev deps
- Run `uv lock` to update the lockfile
- Run `uv sync --all-extras` to install
3. **Type hints**: Add type hints to new code. Run `make check` to verify types.
4. **Before committing**: Run `make fmt` to format, and `make check` and `make test` to verify everything works.
5. **Django shell**: Use `uv run python manage.py shell_plus` (from django-extensions) for an enhanced shell with models auto-imported.
## Notes
- Python 3.13+ required (specified in `pyproject.toml`)
- Database: SQLite (default for Django development)
- No `[build-system]` in pyproject.toml - this is intentional as we're not building a package

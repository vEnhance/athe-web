.PHONY: help install runserver migrate makemigrations createsuperuser check test fmt pre-commit-install pre-commit

help:
	@echo "Available commands:"
	@echo "  make install          - Install dependencies with uv"
	@echo "  make runserver        - Run Django development server"
	@echo "  make migrate          - Apply database migrations"
	@echo "  make makemigrations   - Create new migrations"
	@echo "  make createsuperuser  - Create a Django superuser"
	@echo "  make check            - Run Django checks and type checking"
	@echo "  make test             - Run tests"
	@echo "  make fmt              - Run code formatter"
	@echo "  make pre-commit-install - Install pre-commit hooks"
	@echo "  make pre-commit       - Run pre-commit on all files"

install:
	uv sync --all-extras
	uv run pre-commit install

runserver:
	uv run python manage.py runserver_plus

migrate:
	uv run python manage.py migrate

makemigrations:
	uv run python manage.py makemigrations

createsuperuser:
	uv run python manage.py createsuperuser

check:
	uv run python manage.py check
	uv run python manage.py validate_templates
	uv run pyright .

test:
	uv run pytest

fmt:
	uv run pre-commit run --all-files

pre-commit-install:
	uv run pre-commit install

pre-commit:
	uv run pre-commit run --all-files

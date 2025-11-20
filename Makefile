.PHONY: help install runserver migrate makemigrations createsuperuser check test fmt prek-install prek ci

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
	@echo "  make prek-install     - Install prek hooks"
	@echo "  make prek             - Run prek on all files"
	@echo "  make ci               - Shorthand for fmt + test + check"

install:
	uv sync --all-extras
	uv run prek install

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
	uv run prek run --all-files

prek-install:
	uv run prek install

prek:
	uv run prek run --all-files

ci:
	uv sync --all-extras
	uv run prek install -t pre-commit
	uv run prek run --all-files
	make test
	make check

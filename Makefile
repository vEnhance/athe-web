.PHONY: help install runserver migrate makemigrations createsuperuser check test fmt

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

install:
	uv sync --all-extras

runserver:
	uv run python manage.py runserver

migrate:
	uv run python manage.py migrate

makemigrations:
	uv run python manage.py makemigrations

createsuperuser:
	uv run python manage.py createsuperuser

check:
	uv run python manage.py check
	uv run pyright .

test:
	uv run pytest

fmt:
	uv run ruff format
	uv run ruff check --fix

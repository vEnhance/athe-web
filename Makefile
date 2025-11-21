.PHONY: help install runserver migrate migrations check test fmt

help:
	@echo "Available commands:"
	@echo "  make install          - Install dependencies with uv"
	@echo "  make runserver        - Run Django development server"
	@echo "  make migrate          - Apply database migrations"
	@echo "  make migrations       - Create new migrations"
	@echo "  make check            - Run Django checks and type checking"
	@echo "  make test             - Run tests"
	@echo "  make fmt              - Run code formatter"

install:
	uv sync
	uv run prek install

runserver:
	uv run python manage.py runserver_plus

migrate:
	uv run python manage.py migrate

migrations:
	files=$$(uv run python manage.py makemigrations --scriptable) && \
	if [ -n "$$files" ]; then \
		uv run prek run --files $$files; \
	fi

check:
	uv run python manage.py check
	uv run python manage.py validate_templates
	uv run pyright .

test:
	uv run pytest -n auto

fmt:
	uv run prek run --all-files

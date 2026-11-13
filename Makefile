.PHONY: install assets migrate seed run test lint check

install:
	uv sync --extra dev
	npm install

assets:
	npm run build

migrate:
	.venv/bin/python manage.py migrate

seed:
	.venv/bin/python manage.py seed_demo

run:
	.venv/bin/python manage.py runserver 0.0.0.0:8000

test:
	.venv/bin/pytest

lint:
	.venv/bin/ruff check .
	.venv/bin/ruff format --check .

check:
	.venv/bin/python manage.py check
	.venv/bin/python manage.py makemigrations --check --dry-run

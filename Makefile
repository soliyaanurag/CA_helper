# CA Helper developer commands. Run `make` or `make help` to list them.
#
# Every Python and Node command runs inside the shared conda env through `conda run`
# (never the terminal's activated env, never system Python or a system Node). See CLAUDE.md.
# Works with the old GNU Make 3.81 that ships with macOS.

SHELL := /bin/bash
.DEFAULT_GOAL := help

CONDA ?= conda
ENV_NAME := ca-helper
# `--no-capture-output` streams output live (needed for servers, nicer for tests).
PY := $(CONDA) run --no-capture-output -n $(ENV_NAME)
# Same, but running inside backend/ (where the `app` package and pyproject.toml live).
BACKEND := $(PY) --cwd backend
FLASK := $(BACKEND) flask --app app
# npm from the conda env (Node 22), running inside frontend/.
NPM := $(PY) --cwd frontend npm

.PHONY: help setup env-update infra infra-down migrate migration seed test lint format \
	dev-backend dev-worker dev-frontend

help: ## List all targets
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

# `.env` is required by Docker Compose and the backend. `make setup` creates it.
.env:
	@echo "ERROR: .env is missing. Run 'make setup' (or: cp .env.example .env)." >&2
	@exit 1

setup: ## One-time (and re-runnable) setup: conda env, npm packages, .env
	bash scripts/setup_dev.sh

env-update: ## Sync the conda env after environment.yml / requirements*.txt change
	$(CONDA) env update -n $(ENV_NAME) -f environment.yml --prune

infra: .env ## Start Postgres + Mailpit in Docker and wait until they are ready
	docker compose up -d --wait db mailpit
	@echo "Postgres: localhost:$${DB_HOST_PORT:-5432}   Mailpit UI: http://localhost:8025"

infra-down: ## Stop Postgres + Mailpit (data is kept in the Docker volume)
	docker compose stop db mailpit

migrate: .env ## Apply all migrations (flask db upgrade)
	$(FLASK) db upgrade

migration: .env ## Create a migration: make migration name="onboarding: add business table"
	@if [ -z "$(name)" ]; then echo 'Usage: make migration name="<module>: <message>"' >&2; exit 1; fi
	$(FLASK) db migrate -m "$(name)"

seed: .env ## Insert development seed data (safe to re-run)
	$(FLASK) seed

test: ## Run all tests: pytest (needs `make infra`), then Vitest
	$(BACKEND) pytest
	$(NPM) test

lint: ## Lint + format check: ruff (Python), ESLint + Prettier (frontend)
	$(PY) ruff check backend
	$(PY) ruff format --check backend
	$(NPM) run lint
	$(NPM) run format:check

format: ## Auto-format and auto-fix Python and frontend code
	$(PY) ruff check --fix backend
	$(PY) ruff format backend
	$(NPM) run format

dev-backend: .env ## API with debugger + auto-reload on http://localhost:8000 (python main.py)
	$(BACKEND) python main.py

dev-worker: .env ## Background worker (APScheduler) in the foreground
	$(BACKEND) python worker.py

dev-frontend: ## Vite dev server on http://localhost:5173 (forwards /api to :8000)
	$(NPM) run dev

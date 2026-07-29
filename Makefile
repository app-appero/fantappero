# FantApperò monorepo task runner (EP01-01 / EP01-02 / EP01-03)
# Requires: GNU Make, Docker Compose v2 (local stack), Python 3.12+, Node 20+, pnpm 9
# On Windows without Make, use the equivalent commands in README / docs/development/.
# Bash scripts in infra/scripts/ need Git Bash or WSL on Windows.
# Quality gates (CI parity): docs/development/quality_gates.md

ENV_FILE ?= $(shell if [ -f infra/local/.env ]; then echo infra/local/.env; else echo infra/local/.env.example; fi)
# On Windows, if `bash` resolves to a broken WSL launcher, override:
#   make health BASH="C:/Program Files/Git/bin/bash.exe"
BASH ?= bash

.PHONY: setup setup-js setup-py \
	dev-api dev-web dev-mobile \
	up up-tools down logs health reset-local smoke-local \
	test test-api test-js lint format typecheck build \
	check-migrations migrate migrate-docker migrate-down migrate-check quality smoke help

help:
	@echo "Targets: setup | up | down | logs | health | reset-local | smoke-local |"
	@echo "         dev-api | dev-web | dev-mobile | test | lint | format | typecheck |"
	@echo "         build | migrate | migrate-check | check-migrations | quality | smoke"

setup: setup-js setup-py

setup-js:
	pnpm install

setup-py:
	python -m pip install -e "./backend[dev]"

# --- Local Compose stack (EP01-02 + EP02-01 web) ---

up:
	docker compose --env-file $(ENV_FILE) up -d --build
	$(MAKE) health

up-tools:
	docker compose --env-file $(ENV_FILE) --profile tools up -d --build
	$(MAKE) health

down:
	docker compose --env-file $(ENV_FILE) stop

logs:
	docker compose --env-file $(ENV_FILE) logs -f --tail=100

health:
	$(BASH) infra/scripts/dev_healthcheck.sh

# DESTRUCTIVE: deletes named volumes. Requires CONFIRM=yes
reset-local:
	CONFIRM=$(CONFIRM) $(BASH) infra/scripts/dev_reset.sh

smoke-local:
	$(BASH) infra/scripts/smoke_local_stack.sh

dev-api:
	cd backend && python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

dev-web:
	pnpm --filter @fantappero/web dev

dev-mobile:
	pnpm --filter @fantappero/mobile start

# --- Quality gates (EP01-03; mirrors .github/workflows/ci.yml) ---

test: test-api test-js

test-api:
	cd backend && python -m pytest

test-js:
	pnpm test

lint:
	cd backend && python -m ruff check src tests
	pnpm lint

format:
	cd backend && python -m ruff format --check src tests

typecheck:
	pnpm typecheck

build:
	pnpm run build:packages
	pnpm run build:web
	pnpm --filter @fantappero/mobile build

check-migrations:
	python infra/scripts/check_migrations.py

migrate:
	cd backend && python -m alembic upgrade head

# Prefer on Windows when host DATABASE_URL hits the wrong Postgres on :5432
migrate-docker:
	$(BASH) infra/scripts/migrate_docker.sh

migrate-down:
	cd backend && python -m alembic downgrade base

migrate-check:
	python infra/scripts/check_schema_drift.py

# Local equivalent of required CI jobs (+ migration layout check; drift needs DATABASE_URL)
quality: lint format typecheck test build check-migrations
	@echo "Quality gates passed (lint, format, typecheck, test, build, migrations)."

smoke: test build
	@echo "Smoke checks passed (API tests + JS tests + package/web/mobile type builds)."

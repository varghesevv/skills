# Skills: developer shortcuts. Run `make` or `make help` to list targets.
# Variables can be overridden: make pi-up PI_HOST=ubuntu@192.168.1.50

PI_HOST ?= pi
PI_DIR  ?= skills
PI_PATH := export PATH=$$HOME/.local/bin:$$PATH
# Completes .env if needed, then loads it and builds DATABASE_URL. Secrets are read by the shell only;
# make never expands or prints them.
DB_ENV  := sh scripts/gen-env.sh >/dev/null && set -a && . ./.env && set +a && export DATABASE_URL="postgresql+psycopg://$$POSTGRES_USER:$$POSTGRES_PASSWORD@localhost:$$DB_PORT/$$POSTGRES_DB"
# Node container on the Pi: project mounted at /src, work done in a temp copy at /tmp/w
PI_NODE := docker run --rm -u $$(id -u):$$(id -g) -e HOME=/tmp -v "$$PWD":/src -w /tmp node:22-alpine sh -c
PI_COPY := mkdir w && (cd /src && tar --exclude=node_modules --exclude=dist -cf - .) | tar -xf - -C w && cd w

.DEFAULT_GOAL := help

.PHONY: help env check-secrets install-hooks up down logs ps reset-db be-install be-check be-test be-migrate fe-install fe-check \
	sync-start sync-status sync-stop pi-sync pi-up pi-down pi-ps pi-logs pi-reset-db \
	pi-test pi-check pi-test-web pi-format-web pi-lock-web pi-upgrade-web pi-format pi-shell

help: ## Show this help
	awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

## ---- Secrets ----
env: ## Create or complete .env from .env.example (random database password, existing values kept)
	@sh scripts/gen-env.sh
check-secrets: ## Scan the repository for committed secrets (prints file and line only)
	@sh scripts/check-secrets.sh
install-hooks: ## Run the secret check before every git commit
	@printf '#!/bin/sh\nsh scripts/check-secrets.sh\n' > .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit && echo 'pre-commit hook installed'

## ---- Local Docker stack (run where Docker is installed) ----
up: ## Start db, api, worker, web
	docker compose up -d --build
down: ## Stop the stack (keeps the database)
	docker compose down
logs: ## Follow logs of all services
	docker compose logs -f --tail=100
ps: ## Show service status
	docker compose ps
reset-db: ## Stop the stack and DELETE the database volume
	docker compose down -v

## ---- Backend (needs uv; run on the machine that has it, e.g. the Pi) ----
be-install: ## Install backend dependencies
	cd backend && uv sync
be-check: ## Lint, format check and type check backend
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app
be-test: ## Backend tests incl. PostgreSQL tests (starts db first)
	docker compose up -d --wait db
	$(DB_ENV) && cd backend && uv run pytest
be-migrate: ## Apply database migrations
	docker compose up -d --wait db
	$(DB_ENV) && cd backend && uv run alembic upgrade head

## ---- Frontend (needs Node 22+) ----
fe-install: ## Install frontend dependencies
	cd frontend && npm install
fe-check: ## Lint, format check, type check and test frontend
	cd frontend && npm run lint && npm run format:check && npm run typecheck && npm test

## ---- Mac to Pi file sync (one way, needs Mutagen: see docs) ----
sync-start: ## Start continuous Mac -> Pi sync (Mutagen)
	mutagen sync create --name=skills --sync-mode=one-way-replica --ignore-vcs \
		--ignore=node_modules --ignore=.venv --ignore=__pycache__ --ignore=.env \
		$(CURDIR) $(PI_HOST):$(PI_DIR)
sync-status: ## Show Mutagen sync status
	mutagen sync list skills
sync-stop: ## Stop and remove the Mutagen sync
	mutagen sync terminate skills
pi-sync: ## One-off Mac -> Pi sync with rsync (alternative to Mutagen)
	rsync -az --delete --exclude .git --exclude node_modules --exclude .venv \
		--exclude __pycache__ --exclude .env $(CURDIR)/ $(PI_HOST):$(PI_DIR)/

## ---- Commands that run ON the Pi over SSH (run from the Mac) ----
pi-up: ## Start the stack on the Pi
	ssh $(PI_HOST) 'cd $(PI_DIR) && sh scripts/gen-env.sh && docker compose up -d --build'
pi-down: ## Stop the stack on the Pi
	ssh $(PI_HOST) 'cd $(PI_DIR) && docker compose down'
pi-ps: ## Service status on the Pi
	ssh $(PI_HOST) 'cd $(PI_DIR) && docker compose ps'
pi-logs: ## Follow logs on the Pi (Ctrl-C to stop)
	ssh -t $(PI_HOST) 'cd $(PI_DIR) && docker compose logs -f --tail=100'
pi-reset-db: ## DELETE the database volume on the Pi
	ssh $(PI_HOST) 'cd $(PI_DIR) && docker compose down -v'
pi-check: ## Backend lint, format and type checks on the Pi
	ssh $(PI_HOST) '$(PI_PATH); cd $(PI_DIR)/backend && uv sync && uv run ruff check . && uv run ruff format --check . && uv run mypy app'
pi-test: ## Backend tests (with PostgreSQL) on the Pi
	ssh $(PI_HOST) '$(PI_PATH); cd $(PI_DIR) && $(DB_ENV) && docker compose up -d --wait db && cd backend && uv sync && uv run pytest'
pi-test-web: ## Frontend lint, type check and tests on the Pi (uses Docker, no Node needed)
	ssh $(PI_HOST) 'cd $(PI_DIR)/frontend && docker run --rm -v "$$PWD":/app -v skills_node_modules:/app/node_modules -w /app node:22-alpine sh -c "npm install && npm run lint && npm run format:check && npm run typecheck && npm test"'
pi-format-web: ## Auto-format the frontend with Prettier on the Pi and pull the result back (also creates package-lock.json)
	$(MAKE) pi-sync
	ssh $(PI_HOST) 'cd $(PI_DIR)/frontend && $(PI_NODE) "$(PI_COPY) && npm install && npx prettier --write . && tar --exclude=node_modules --exclude=dist -cf - . | tar -xf - -C /src"'
	rsync -rlt --exclude node_modules --exclude dist $(PI_HOST):$(PI_DIR)/frontend/ $(CURDIR)/frontend/
	@echo "Formatted files copied back to frontend/. Review with git diff, then commit."
pi-lock-web: ## Generate frontend/package-lock.json on the Pi (Docker, no Node needed) and copy it back
	$(MAKE) pi-sync
	ssh $(PI_HOST) 'cd $(PI_DIR)/frontend && $(PI_NODE) "$(PI_COPY) && npm install --package-lock-only && cp package-lock.json /src/"'
	rsync -t $(PI_HOST):$(PI_DIR)/frontend/package-lock.json $(CURDIR)/frontend/package-lock.json
	@ls -l frontend/package-lock.json
pi-upgrade-web: ## Try upgrading vite/vitest/plugin-react on the Pi; keeps the change only if lint, types, tests, build and audit all pass
	$(MAKE) pi-sync
	ssh $(PI_HOST) 'cd $(PI_DIR)/frontend && $(PI_NODE) "$(PI_COPY) && npm install && npm install -D vite@latest vitest@latest @vitejs/plugin-react@latest && npm run lint && npm run format:check && npm run typecheck && npm test && npm run build && npm audit --audit-level=high && cp package.json package-lock.json /src/"'
	rsync -t $(PI_HOST):$(PI_DIR)/frontend/package.json $(PI_HOST):$(PI_DIR)/frontend/package-lock.json $(CURDIR)/frontend/
	@git diff --stat -- frontend/package.json frontend/package-lock.json
pi-format: ## Auto-fix and format the backend with Ruff on the Pi, then copy the result back
	$(MAKE) pi-sync
	ssh $(PI_HOST) '$(PI_PATH); cd $(PI_DIR)/backend && uv run ruff check --fix . && uv run ruff format .'
	rsync -rlt --exclude .venv --exclude __pycache__ --exclude .pytest_cache --exclude .mypy_cache --exclude .ruff_cache $(PI_HOST):$(PI_DIR)/backend/ $(CURDIR)/backend/
	@git diff --stat -- backend | tail -3
pi-shell: ## Open a shell in the project folder on the Pi
	ssh -t $(PI_HOST) 'cd $(PI_DIR) && exec $$SHELL -l'

# Consulting Research Agent — root Makefile
#
# Common targets for running the local development stack.
# Infra (Postgres + pgvector) lives under infra/. Backend under backend/. Frontend under frontend/.

COMPOSE := docker compose -f infra/docker-compose.yml

.PHONY: db-up db-down db-logs db-shell migrate migrate-rev dev check check-integration precommit-install help

help:
	@echo "Targets:"
	@echo "  db-up                Start Postgres+pgvector in the background"
	@echo "  db-down              Stop Postgres and remove the container (named volume persists)"
	@echo "  db-logs              Tail Postgres logs"
	@echo "  db-shell             Open a psql shell inside the running Postgres container"
	@echo "  migrate              Apply Alembic migrations (alembic upgrade head)"
	@echo "  migrate-rev m=\"msg\"  Autogenerate a new Alembic revision"
	@echo "  dev                  Start db, backend (uvicorn) and frontend (pnpm); Ctrl+C cleans up"
	@echo "  check                Run lint + typecheck + fast tests for backend & frontend"
	@echo "  check-integration    Run backend integration tests (requires 'make db-up')"
	@echo "  precommit-install    Install pre-commit git hook into .git/hooks/"

db-up:
	$(COMPOSE) up -d postgres

db-down:
	$(COMPOSE) down

db-logs:
	$(COMPOSE) logs -f postgres

db-shell:
	$(COMPOSE) exec postgres psql -U consulting -d consulting

migrate:
	cd backend && uv run alembic upgrade head

migrate-rev:
	@if [ -z "$(m)" ]; then echo "usage: make migrate-rev m=\"message\""; exit 2; fi
	cd backend && uv run alembic revision --autogenerate -m "$(m)"

dev: db-up
	@trap 'kill 0' INT TERM EXIT; \
	(cd backend && uv run uvicorn app.main:app --reload --port 8000) & \
	(cd frontend && pnpm dev) & \
	wait

check:
	bash scripts/check.sh

# Integration tests hit a real Postgres. Make sure `make db-up` is running.
check-integration:
	cd backend && uv run pytest tests/integration -v

precommit-install:
	# Installs only the default `pre-commit` hook type (.git/hooks/pre-commit).
	# For pre-push or commit-msg hooks, re-run with --hook-type, e.g.:
	#   cd backend && uv run pre-commit install --hook-type pre-push
	cd backend && uv run pre-commit install

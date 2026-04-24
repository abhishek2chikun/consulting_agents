# Backend — agent.md

Project-level discoverability file for the Consulting Research Agent backend.
Child modules own their internal details through their own `agent.md` files.

## How to use this system

Every module/submodule under `backend/app/` carries an `agent.md` describing its status,
purpose, public API, dependencies, and next steps. When you need to understand or change
a module, read its `agent.md` first, then this file for cross-module context. Update the
relevant `agent.md` whenever you change a module's surface area, dependencies, or status.

## Project overview

FastAPI-based backend for the Consulting Research Agent V1. Async SQLAlchemy + PostgreSQL
for persistence, Pydantic for validation, Fernet for at-rest secret encryption. Currently
at the scaffolding stage — only the health endpoint is wired.

## Directory structure

```text
backend/
  pyproject.toml        # project + deps (uv-managed)
  ruff.toml             # lint config (line-length 100, py312)
  mypy.ini              # strict typecheck, tests excluded
  alembic.ini           # alembic config (script_location = alembic)
  .env.example          # env var template
  .gitignore
  README.md
  agent.md              # this file
  app/
    __init__.py
    main.py             # create_app() + /health
    agent.md
    core/
      __init__.py
      config.py         # Settings (pydantic-settings)
      db.py             # async engine, session, Base
      agent.md
  alembic/              # migrations (async env.py); see alembic/agent.md
    env.py
    script.py.mako
    versions/
      0001_baseline.py
  tests/
    __init__.py
    test_health.py
    integration/
      __init__.py
      test_db.py        # hits real Postgres via AsyncSessionLocal
```

## Module registry

| Module | Status | Location | agent.md |
|---|---|---|---|
| `app` | Boilerplate | `backend/app/` | `backend/app/agent.md` |
| `app.core` | Scaffolding | `backend/app/core/` | `backend/app/core/agent.md` |
| `alembic` | Scaffolding (baseline only) | `backend/alembic/` | `backend/alembic/agent.md` |

## Conventions

- **Python:** 3.12+ (project pin in `pyproject.toml`).
- **Package manager:** `uv` exclusively. Never invoke `pip` directly.
- **TDD:** every behavior change starts with a failing test under `tests/`.
- **Lint/Type:** `ruff` (line-length 100) + `mypy --strict` on `app/`. Tests are excluded
  from mypy strictness.
- **Settings:** all runtime configuration flows through `app.core.config.Settings`
  (loaded from environment / `.env`).
- **Commits:** Conventional Commits, one commit per plan task.
- **Imports:** canonical `app.<module>` style; no relative imports across packages.

## Quality gates

Two layers of automation enforce backend lint/type/test discipline:

1. **`scripts/check.sh`** (root) — runs `ruff check`, `ruff format --check`,
   `mypy app`, and `pytest --ignore=tests/integration` for the backend, then
   `pnpm install --frozen-lockfile`, `pnpm lint`, and `pnpm typecheck` for
   the frontend. `pnpm build` is gated behind `CHECK_BUILD=1` (CI sets it;
   local default skips it for speed). Integration tests are excluded so the
   gate stays runnable without Postgres. Invoke via `make check` or
   `CHECK_BUILD=1 bash scripts/check.sh`.
2. **Pre-commit hooks** (`.pre-commit-config.yaml`) — ruff (auto-fix),
   ruff-format, and a `local` mypy hook that runs `uv run mypy app` against
   the real backend venv (chosen over `mirrors-mypy` to avoid drift between
   `additional_dependencies` and `uv.lock`). Frontend hooks shell out to
   `pnpm lint` and `pnpm typecheck`. No JS/TS formatter is configured yet —
   `eslint.config.mjs` carries no formatting rules; this is a known V1
   scaffolding gap and will likely be addressed by adding prettier in M2 or
   later.

`pre-commit` is a backend dev dependency, so all hooks run via
`uv run pre-commit ...` with no extra tooling on the host. Opt in to the
git hook with `make precommit-install`. Run hooks ad-hoc with
`cd backend && uv run pre-commit run --all-files`.

DB-backed integration tests run separately: `make db-up && make check-integration`.

## Verification commands

Run from `backend/`:

```bash
uv sync --dev
uv run pytest -v                  # integration tests need `make db-up`
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run alembic upgrade head       # apply migrations to local Postgres
```

Tests are split into:

- `backend/tests/` — unit / fast tests (e.g. `test_health.py`).
- `backend/tests/integration/` — hit real services (Postgres, etc.).
  Require `make db-up` and a working `DATABASE_URL`.

## Progress

- M1.1 — FastAPI scaffold + `/health` endpoint + Settings: **Done**.
- M1.3 — Local infra (Postgres 16 + pgvector) via Docker Compose at `infra/docker-compose.yml`; root `Makefile` exposes `db-up`/`db-down`/`db-logs`/`db-shell`/`dev`. Connect via `DATABASE_URL=postgresql+asyncpg://consulting:consulting@localhost:5432/consulting`: **Done**.
- M1.4 — Async DB session (`app.core.db`: `engine`, `AsyncSessionLocal`, `get_session`, `Base`) + Alembic baseline (`alembic/`, revision `0001`). Root `Makefile` adds `migrate` and `migrate-rev m="..."`. Integration test `tests/integration/test_db.py::test_db_session_can_select_one` covers it: **Done**.
- M1.5 — Quality gates: `scripts/check.sh` (backend lint/format/mypy/unit tests + frontend install/lint/typecheck/build), `.pre-commit-config.yaml` (ruff, ruff-format, local mypy via uv venv, eslint, tsc), `pre-commit` added to backend dev deps, root `Makefile` exposes `check`, `check-integration`, `precommit-install`: **Done**.

## Deferred work

Everything else in the V1 plan (M1.2 onward): database/Alembic, auth, agent runtime,
websockets, retrieval, exports, frontend integration. See `docs/` for the full plan.

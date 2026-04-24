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
exposes `/health`, the M2.4 Settings REST API (`/settings/*`), and the M2.6 `/ping`
smoke-test endpoint.

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
    main.py             # create_app() + /health + mounted routers
    agent.md
    core/
      __init__.py
      config.py         # Settings (pydantic-settings)
      db.py             # async engine, session, Base
      crypto.py         # Fernet wrap/unwrap helpers
      agent.md
    models/
      __init__.py       # ORM registry / re-exports
      user.py           # User + SINGLETON_USER_ID
      settings_kv.py    # SettingKV (composite-PK JSONB store)
      provider_key.py   # ProviderKey (encrypted provider API keys)
      agent.md
    services/
      __init__.py
      settings_service.py  # SettingsService (provider keys + JSON KV)
      agent.md
    schemas/
      __init__.py
      settings.py       # Settings API Pydantic DTOs (M2.4)
      ping.py           # /ping request/response DTOs (M2.6)
      agent.md
    api/
      __init__.py
      settings.py       # Settings REST router (M2.4)
      ping.py           # Ping smoke-test router (M2.6)
      agent.md
    agents/
      __init__.py       # re-exports get_chat_model, provider_name_for, ... (M2.6)
      llm.py            # LLM provider registry + get_chat_model + provider_name_for (M2.5/M2.6)
      agent.md
  alembic/              # migrations (async env.py); see alembic/agent.md
    env.py
    script.py.mako
    versions/
      0001_baseline.py
      0002_users_and_settings.py
      0003_provider_keys.py
  tests/
    __init__.py
    test_health.py
    unit/
      __init__.py
      test_crypto.py    # Fernet wrap/unwrap (no DB, runs in `make check`)
      test_llm_registry.py # PROVIDER_REGISTRY + get_chat_model (M2.5/M2.6, fully mocked)
    integration/
      __init__.py
      test_db.py             # hits real Postgres via AsyncSessionLocal
      test_settings_kv.py    # upsert + read against settings_kv
      test_settings_service.py  # encrypted-at-rest provider key storage
      test_settings_api.py   # Settings REST API (M2.4) end-to-end
      test_ping.py           # /ping endpoint (M2.6) with monkeypatched chat model
```

## Module registry

| Module | Status | Location | agent.md |
|---|---|---|---|
| `app` | Active scaffolding (M2.6) | `backend/app/` | `backend/app/agent.md` |
| `app.core` | Scaffolding (config + db + crypto) | `backend/app/core/` | `backend/app/core/agent.md` |
| `app.models` | Active (M2.3) | `backend/app/models/` | `backend/app/models/agent.md` |
| `app.services` | Active (M2.4) | `backend/app/services/` | `backend/app/services/agent.md` |
| `app.schemas` | Active (M2.6) | `backend/app/schemas/` | `backend/app/schemas/agent.md` |
| `app.api` | Active (M2.6) | `backend/app/api/` | `backend/app/api/agent.md` |
| `app.agents` | Active (M2.6) | `backend/app/agents/` | `backend/app/agents/agent.md` |
| `alembic` | Active (revisions 0001, 0002, 0003) | `backend/alembic/` | `backend/alembic/agent.md` |

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

- `backend/tests/` — unit / fast tests (e.g. `test_health.py`,
  `tests/unit/test_crypto.py`).
- `backend/tests/integration/` — hit real services (Postgres, etc.).
  Require `make db-up` and a working `DATABASE_URL`.

## Progress

- M1.1 — FastAPI scaffold + `/health` endpoint + Settings: **Done**.
- M1.3 — Local infra (Postgres 16 + pgvector) via Docker Compose at `infra/docker-compose.yml`; root `Makefile` exposes `db-up`/`db-down`/`db-logs`/`db-shell`/`dev`. Connect via `DATABASE_URL=postgresql+asyncpg://consulting:consulting@localhost:5432/consulting`: **Done**.
- M1.4 — Async DB session (`app.core.db`: `engine`, `AsyncSessionLocal`, `get_session`, `Base`) + Alembic baseline (`alembic/`, revision `0001`). Root `Makefile` adds `migrate` and `migrate-rev m="..."`. Integration test `tests/integration/test_db.py::test_db_session_can_select_one` covers it: **Done**.
- M1.5 — Quality gates: `scripts/check.sh` (backend lint/format/mypy/unit tests + frontend install/lint/typecheck/build), `.pre-commit-config.yaml` (ruff, ruff-format, local mypy via uv venv, eslint, tsc), `pre-commit` added to backend dev deps, root `Makefile` exposes `check`, `check-integration`, `precommit-install`: **Done**.
- M2.1 — `users` and `settings_kv` tables. ORM models in `app/models/` (`User` + `SINGLETON_USER_ID = '00000000-…-0001'`, `SettingKV` with composite PK `(user_id, key)` and JSONB `value`). Alembic revision `0002_users_and_settings` creates both tables and seeds the singleton user via raw SQL (idempotent via `ON CONFLICT DO NOTHING`). Integration test `tests/integration/test_settings_kv.py::test_upsert_and_read_setting` covers ON CONFLICT upsert + read-back. `pyproject.toml` now sets `asyncio_default_test_loop_scope = "session"` so the module-level async engine survives across tests: **Done**.
- M2.2 — Fernet crypto helper (`app/core/crypto.py`): `wrap` / `unwrap` / `generate_key` over `cryptography.fernet.Fernet`, key sourced from `settings.fernet_key` on every call (no cached cipher). Unconfigured key raises `ValueError("FERNET_KEY not configured")`; `InvalidToken` is allowed to propagate from `unwrap`. New `tests/unit/` tree (with `__init__.py`) holding `test_crypto.py` — 6 tests: roundtrip, wrong-key, IV uniqueness, empty-token, unconfigured-key, key generation. Pytest auto-discovers `tests/unit/` so `scripts/check.sh` (which uses `--ignore=tests/integration` ) picks them up without changes: **Done**.
- M2.3 — `provider_keys` table + `SettingsService`. ORM `ProviderKey` (UUID PK, FK `users.id` ON DELETE CASCADE indexed, `provider` String(64), `encrypted_key` Text, timestamptz `created_at`/`updated_at`, unique constraint `uq_provider_keys_user_provider` on `(user_id, provider)`). Alembic revision `0003_provider_keys` (round-trip clean; `alembic check` reports no drift). New `app/services/` package with `SettingsService(session)` exposing `set_provider_key(provider, key)` (Fernet wrap → Postgres `ON CONFLICT (user_id, provider) DO UPDATE`) and `get_provider_key(provider) -> str | None` (Fernet unwrap). Lowercases + strips `provider`; rejects empty inputs with `ValueError`. Three integration tests in `tests/integration/test_settings_service.py` — including a raw `SELECT encrypted_key` confirming the column never contains plaintext (asserts the Fernet `"gAAAAA"` token prefix): **Done**.
- M2.4 — Settings REST API. New packages `app/schemas/` (Pydantic v2 DTOs: `ProvidersResponse`, `SetProviderKeyRequest`, `ModelOverridesRequest`, `SearchProviderRequest` with `Literal["tavily","exa","perplexity"]`, `MaxStageRetriesRequest` with `1..5`, `SettingsSnapshot`) and `app/api/` (`settings.py` router mounted at `/settings` via `app.main.create_app`). `SettingsService` extended with `list_provider_keys`, `get_setting`, `set_setting`, `get_settings_snapshot`; module-level `KNOWN_PROVIDERS` (anthropic, openai, google, aws, ollama, tavily, exa, perplexity) and `DEFAULT_MAX_STAGE_RETRIES = 2`. Endpoints: `GET /settings/providers`, `PUT /settings/providers/{provider}`, `PUT /settings/model_overrides`, `PUT /settings/search_provider`, `PUT /settings/max_stage_retries`, `GET /settings`. PUTs return 204; validation errors return 422. Provider keys are NEVER exposed in any response (only `has_key: bool` flags); pinned by a defensive `test_get_providers_never_exposes_raw_key` test that scans response bodies for the raw plaintext substring. 14 integration tests in `tests/integration/test_settings_api.py` (covering 7 spec behaviors + parametrized boundary rejects + snapshot defaults). Dependencies wired via `Annotated[T, Depends(...)]` aliases to keep ruff `B008` clean. Smoke-verified: `curl /openapi.json` lists all six paths; `GET /settings` on a fresh DB returns sensible defaults: **Done**.
- M2.5 — LLM provider registry + `get_chat_model`. New `app/agents/` package with `llm.py` exposing `PROVIDER_REGISTRY` (anthropic, openai, google, aws, ollama), `LLM_PROVIDERS`, `DEFAULT_PROVIDER = "anthropic"`, and `get_chat_model(role, *, session)`. Resolution order: `settings_kv["model_overrides"]["overrides"][role]` → fallback to `DEFAULT_PROVIDER` + provider's `default_model`. Validates provider against registry (`ValueError` on unknown), enforces `requires_key` per provider (`ValueError` when missing), Ollama bypasses the key requirement. AWS Bedrock entry registered but factory raises `NotImplementedError` (deferred to V1.1 — Bedrock needs multi-part credentials the V1 single-key schema doesn't express). No client caching. Six new deps in main group: `langchain-core`, `langchain-anthropic`, `langchain-openai`, `langchain-google-genai`, `langchain-aws`, `langchain-ollama` (lockfile grew with boto3, google-cloud-aiplatform, etc. — expected). Seven mocked unit tests in `tests/unit/test_llm_registry.py` cover override, default, missing-key, unknown-provider, Ollama no-key, AWS not-implemented, and registry-keys-match: **Done**.
- M2.6 — `/ping` smoke-test endpoint + M2.5 review fold-ins. New `app/schemas/ping.py` (`PingRequest` with prompt 1..10_000 chars and optional `role` defaulting to `"framing"`; `PingResponse` with `response`, `model`, `provider`) and `app/api/ping.py` (router mounted at `/ping` via `app.main.create_app`). `POST /ping` resolves a chat model via `app.agents.get_chat_model(role, ...)`, invokes it with `[HumanMessage(content=prompt)]`, and returns the echoed text plus model/provider labels (provider derived via the new `provider_name_for(model)` helper backed by `_CLASS_TO_PROVIDER`). Errors map: `ValueError` (missing key / unknown provider) → 400, `NotImplementedError` (AWS Bedrock deferral) → 501, anything else falls through to FastAPI's 500. Six integration tests in `tests/integration/test_ping.py` use `monkeypatch.setattr(app.api.ping, "get_chat_model", ...)` with a `FakeChatModel` to avoid any real API call. Folded-in M2.5 review minors: (a) added matching `# type: ignore[arg-type]` rationale comment to `_openai_factory`; (b) parametrized empty-role unit test (`""` / `"   "`) pinning the existing module-level guard; (c) `app/agents/__init__.py` now re-exports `get_chat_model`, `provider_name_for`, `PROVIDER_REGISTRY`, `LLM_PROVIDERS`, `DEFAULT_PROVIDER` (mirrors `app.models`). Live smoke (no anthropic key configured) returns 400 with `"No API key configured for provider 'anthropic'"`; `/openapi.json` lists `/ping`. All 41 tests pass (33 prior + 6 ping + 2 parametrized empty-role); `make check` and `make check-integration` both green: **Done**.
- M2.7 (frontend pair) — `app.main.create_app` now installs `CORSMiddleware` allowing `http://localhost:3000` and `http://127.0.0.1:3000` (V1 single-user local dev), methods `GET/PUT/POST/OPTIONS`, header `Content-Type`. `allow_credentials=False` because there's no auth in V1. The origin list is a module-level constant (`ALLOWED_ORIGINS`); when V1.1 adds auth or remote deployment it will move into `Settings`. No other backend changes — the Settings/Ping APIs themselves are untouched, all 41 tests still pass: **Done**.

## M2 milestone

All M2 sub-tasks (M2.1 through M2.6) are complete and locally green
but **uncommitted on `main`**. Pending: squash all M2 work into a
single conventional-commits commit (per the milestone-commit policy
documented in the V1 plan).

## Deferred work

Everything else in the V1 plan (M1.2 onward): database/Alembic, auth, agent runtime,
websockets, retrieval, exports, frontend integration. See `docs/` for the full plan.

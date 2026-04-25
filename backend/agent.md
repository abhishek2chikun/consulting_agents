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
exposes `/health`, the M2.4 Settings REST API (`/settings/*`), the M2.6 `/ping`
smoke-test endpoint, the M3.1 task catalog (`GET /tasks`), and the M3.3
documents API (`POST/GET /documents`, `DELETE /documents/{id}`).

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
      task_registry.py  # in-process asyncio.Task registry (M3.6)
      agent.md
    models/
      __init__.py       # ORM registry / re-exports
      user.py           # User + SINGLETON_USER_ID
      settings_kv.py    # SettingKV (composite-PK JSONB store)
      provider_key.py   # ProviderKey (encrypted provider API keys)
      task_type.py      # TaskType (consulting workflow catalog row)
      document.py       # Document + DocumentStatus enum
      chunk.py          # Chunk (text span + pgvector embedding + HNSW index)
      agent.md
    services/
      __init__.py
      settings_service.py  # SettingsService (provider keys + JSON KV)
      document_service.py  # DocumentService (upload binary + Document row lifecycle, M3.3)
      agent.md
    schemas/
      __init__.py
      settings.py       # Settings API Pydantic DTOs (M2.4)
      ping.py           # /ping request/response DTOs (M2.6)
      tasks.py          # /tasks catalog DTO (M3.1)
      documents.py      # /documents response DTO (M3.3)
      agent.md
    api/
      __init__.py
      settings.py       # Settings REST router (M2.4)
      ping.py           # Ping smoke-test router (M2.6)
      tasks.py          # Tasks catalog router (M3.1)
      documents.py      # Documents REST router (M3.3)
      agent.md
    agents/
      __init__.py       # re-exports get_chat_model, provider_name_for, ... (M2.6)
      llm.py            # LLM provider registry + get_chat_model + provider_name_for (M2.5/M2.6)
      tools/            # M3.7 — @tool-decorated callables bound by agent nodes
        __init__.py
        rag_search.py   # @tool rag_search — pgvector cosine over chunks
        agent.md
      agent.md
    ingestion/
      __init__.py
      docling_parser.py # Synchronous Docling wrapper (parse_to_markdown) (M3.4)
      chunker.py        # Token-aware chunker (chunk → list[ChunkPayload]) (M3.5)
      embedder.py       # OpenAI embedding wrapper (text-embedding-3-small, 1536) (M3.6)
      worker.py         # async run_ingest pipeline driver (M3.6)
      agent.md
  alembic/              # migrations (async env.py); see alembic/agent.md
    env.py
    script.py.mako
    versions/
      0001_baseline.py
      0002_users_and_settings.py
      0003_provider_keys.py
      0004_task_catalog.py
      0005_documents_and_chunks.py
  tests/
    __init__.py
    test_health.py
    unit/
      __init__.py
      test_crypto.py    # Fernet wrap/unwrap (no DB, runs in `make check`)
      test_llm_registry.py # PROVIDER_REGISTRY + get_chat_model (M2.5/M2.6, fully mocked)
      test_docling_parser.py # parse_to_markdown wrapper (M3.4, marked @pytest.mark.slow)
      test_chunker.py        # token-aware chunk() unit tests (M3.5)
      test_task_registry.py  # in-process asyncio.Task registry (M3.6)
      test_rag_search.py     # rag_search early-exit paths (M3.7, no DB / no network)
      test_search_provider_base.py # SearchResult schema round-trip (M4.1)
      test_tavily_provider.py # Tavily adapter normalization with respx (M4.2)
      test_exa_provider.py    # Exa adapter normalization with respx (M4.3)
      test_perplexity_provider.py # Perplexity adapter normalization with respx (M4.4)
    integration/
      __init__.py
      conftest.py            # autouse fixture draining `ingest:*` tasks after each test (M3.6)
      test_db.py             # hits real Postgres via AsyncSessionLocal
      test_settings_kv.py    # upsert + read against settings_kv
      test_settings_service.py  # encrypted-at-rest provider key storage
      test_settings_api.py   # Settings REST API (M2.4) end-to-end
      test_ping.py           # /ping endpoint (M2.6) with monkeypatched chat model
      test_tasks_catalog.py  # GET /tasks returns seeded catalog (M3.1)
      test_documents_orm.py  # Document + Chunk ORM round-trip with pgvector (M3.2)
      test_documents_api.py  # Documents REST API (M3.3) end-to-end
      test_ingest_pipeline.py # M3.6 end-to-end: upload → run_ingest → ready (skipped without OPENAI_API_KEY)
      test_rag_search.py     # M3.7 end-to-end: ingest → rag_search returns relevant chunk (skipped without OPENAI_API_KEY)
      test_health_search.py  # /health/search diagnostics endpoint (M4.7)
    fixtures/
      README.md              # how to regenerate sample.pdf
      sample.pdf             # 2-page deterministic PDF for ingestion tests (M3.4)
```

## Module registry

| Module | Status | Location | agent.md |
|---|---|---|---|
| `app` | Active scaffolding (M4.7) | `backend/app/` | `backend/app/agent.md` |
| `app.core` | Active (config + db + crypto + task_registry) | `backend/app/core/` | `backend/app/core/agent.md` |
| `app.models` | Active (M3.2) | `backend/app/models/` | `backend/app/models/agent.md` |
| `app.services` | Active (M3.3) | `backend/app/services/` | `backend/app/services/agent.md` |
| `app.schemas` | Active (M3.3) | `backend/app/schemas/` | `backend/app/schemas/agent.md` |
| `app.api` | Active (M4.7) | `backend/app/api/` | `backend/app/api/agent.md` |
| `app.agents` | Active (M4.4) | `backend/app/agents/` | `backend/app/agents/agent.md` |
| `app.ingestion` | Active (M3.6) | `backend/app/ingestion/` | `backend/app/ingestion/agent.md` |
| `alembic` | Active (revisions 0001, 0002, 0003, 0004, 0005) | `backend/alembic/` | `backend/alembic/agent.md` |

## Conventions

- **Python:** 3.12+ (project pin in `pyproject.toml`).
- **Package manager:** `uv` exclusively. Never invoke `pip` directly.
- **TDD:** every behavior change starts with a failing test under `tests/`.
- **Lint/Type:** `ruff` (line-length 100) + `mypy --strict` on `app/`. Tests are excluded
  from mypy strictness.
- **Settings:** all runtime configuration flows through `app.core.config.Settings`
  (loaded from environment / `.env`).
- **Commits:** Conventional Commits, one commit per milestone (M1, M2, M3, ...).
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
- M3.1 — `tasks_catalog` table seeded with `market_entry` + `ma`. New ORM `TaskType` (slug PK, name, description, enabled with both ORM `default=False` and `server_default=text("false")` for autogenerate parity). Alembic revision `0004_task_catalog` creates the table and seeds the V1 catalog via parameterised `op.execute(sa.text(...).bindparams(...))` with `ON CONFLICT (slug) DO NOTHING`. New `app/schemas/tasks.py` (`TaskTypeInfo` — `slug`, `name`, `description`, `enabled`) and `app/api/tasks.py` (router mounted at `/tasks`). `GET /tasks` returns a **bare list** (`list[TaskTypeInfo]`) ordered by slug, matching the spec test's literal response shape — no `{tasks: [...]}` envelope. Two integration tests in `tests/integration/test_tasks_catalog.py` pin the seeded rows and the sort order. `alembic check` clean; downgrade → upgrade round-trip re-seeds correctly. Live smoke against uvicorn returns the expected JSON array of two task types: **Done**.
- M3.2 — `documents` and `chunks` tables with pgvector HNSW index. New deps: `pgvector` (main) and `numpy` (dev, used only by tests for random embeddings). New setting `embedding_dim: int = 1536` in `app.core.config.Settings` (env: `EMBEDDING_DIM`). New ORM `Document` (id UUID PK, user_id FK indexed ON DELETE CASCADE, filename, mime, size, status native Postgres enum `document_status` with values pending|parsing|embedding|ready|failed defaulting to pending, error nullable, timestamptz created_at/updated_at) and `Chunk` (id UUID PK, document_id FK indexed ON DELETE CASCADE, ord int, text, embedding `vector(N)` with N from `Settings.embedding_dim` evaluated at import time, embedding_model String(128), `metadata_` Python attr → `metadata` JSONB column server_default `'{}'::jsonb` because `metadata` collides with `DeclarativeBase.metadata`). `DocumentStatus` is an `enum.StrEnum` for stringly-typed values that pass ruff's enum lint. Alembic revision `0005_documents_and_chunks` creates both tables; the `chunks.embedding` column uses `Vector(int(os.environ.get("EMBEDDING_DIM", "1536")))` so the dim is sourced from the env var at migration execution time (no Python settings cache needed). HNSW index `ix_chunks_embedding_hnsw` on `chunks.embedding` with `vector_cosine_ops` is created via raw `op.execute("CREATE INDEX ...")` — Alembic has no built-in HNSW DDL helper. ORM declares the same index in `Chunk.__table_args__` so `alembic check` reports no drift. `mypy.ini` adds `[mypy-pgvector.*] ignore_missing_imports = True` because pgvector ships no `py.typed` marker. Integration test `tests/integration/test_documents_orm.py::test_insert_document_and_chunk_roundtrip` inserts a Document + a Chunk with a numpy-random embedding and reads it back, asserting dim, prefix values, and metadata. 44/44 tests pass; downgrade → upgrade round-trip re-creates the HNSW index cleanly: **Done**.
- M3.3 — Document upload API (no ingest yet). New `app.schemas.documents.DocumentInfo` (id, filename, mime, size, status, error, created_at, updated_at; `from_attributes=True`), new `app.services.document_service.DocumentService` (single-user, commits inside; create flushes row → writes file → commits so a write failure rolls back; delete commits row removal first then unlinks file `missing_ok=True` because the DB is the source of truth), new `app.api.documents` router mounted at `/documents` (`POST` multipart `file=UploadFile` → 201 `DocumentInfo`, `GET` → `list[DocumentInfo]`, `DELETE /{doc_id}` → 204/404; empty filename or zero bytes → 400). New `Settings.upload_dir: Path = Path("data/uploads")` (env: `UPLOAD_DIR`) read fresh on every service call via `get_settings()`. CORS `allow_methods` extended to include `DELETE`. New runtime dep: `python-multipart` (FastAPI requires it for multipart parsing). `data/` added to root `.gitignore`. Five integration tests in `tests/integration/test_documents_api.py` use a per-test `tmp_path` UPLOAD_DIR override (with `get_settings.cache_clear()`) and an autouse async DB cleanup, covering all success + error paths. 49/49 tests pass; `ruff`, `ruff format`, `mypy app`, and `alembic check` all clean. Live smoke against uvicorn round-trips a text file end-to-end (POST returns `status: pending`, file written to `data/uploads/`, GET lists it): **Done**.
- M3.4 — Docling parser wrapper. New runtime dep `docling` 2.91 (heavy transitive tree: torch, transformers, OCR libs — expected, V1 chose Docling for parser quality). New `app/ingestion/` package containing `docling_parser.parse_to_markdown(path) -> tuple[str, dict[str, Any]]`. Synchronous and blocking — designed to be wrapped in `asyncio.to_thread` by the M3.6 worker; never call from a request handler directly. Returns `(markdown, {"page_count": int, "source_format": str})`. Verified against Docling 2.91: `result.document` is a `DoclingDocument`, `pages` is a `dict[int, PageItem]` so `len(document.pages)` yields the page count; `export_to_markdown()` returns clean markdown. Defensive fallback to `document.num_pages()` if the `pages` shape changes upstream. New 2-page deterministic fixture `backend/tests/fixtures/sample.pdf` (1.8KB) generated with `reportlab` in an isolated `uv run --with reportlab` env — `reportlab` is **not** a project dep; regeneration recipe lives in `backend/tests/fixtures/README.md`. Three unit tests in `tests/unit/test_docling_parser.py`: fixture-existence guard, end-to-end parse (asserts `page_count == 2`, `source_format == "pdf"`, and recognisable text in markdown — marked `@pytest.mark.slow` because the first run downloads ~hundreds of MB of layout/OCR weights from Hugging Face), and `FileNotFoundError` for missing path. New marker registered in `pyproject.toml` (`markers = ["slow: ..."]`). `mypy.ini` adds `[mypy-docling.*] ignore_missing_imports = True` (docling lacks `py.typed`). 52/52 tests pass after first-run model download. Per V1 milestone-commit policy this work is **uncommitted** on `main` and will squash into the M3 commit after M3.7: **Done**.
- M3.5 — Token-aware chunker. New runtime dep `tiktoken` (ships `py.typed`, no mypy stub config needed). New module `app/ingestion/chunker.py` exposing `ChunkPayload(ord:int, text:str)` (frozen dataclass) and `chunk(markdown, target_tokens=800, overlap_tokens=100) -> list[ChunkPayload]`. Implementation: encode the stripped input with tiktoken's `cl100k_base` BPE (GPT-4 / Claude 3 family compatible — adequate for SIZING; not exact for billing), walk a sliding window of `target_tokens` with stride `target_tokens - overlap_tokens`, decode each window and `strip()` whitespace, suppress trailing empty windows, and densely renumber `ord`. Returns `[]` for empty/whitespace input; returns one chunk when the whole input fits in `target_tokens`. Validates `target_tokens > 0` and `0 <= overlap_tokens < target_tokens`. Pure CPU, fast — no async wrapping needed by the M3.6 worker. Known V1 limitation: window boundaries land between BPE tokens, not on sentence/markdown structure (M5+ may revisit). Seven fast unit tests in `tests/unit/test_chunker.py` cover: short-text single-chunk, long-text size bound (with ±5 token leeway for decode/strip drift), boundary overlap (asserts ≥40/80 token IDs match between consecutive chunks' tail/head), order preservation (`ord` is 0..N-1 and word0/word1999 land in first/last chunk respectively), empty + whitespace input, arg validation (zero/negative/equal-to-target overlap), and `ChunkPayload` dataclass identity. 59/59 tests pass; `ruff`, `ruff format`, `mypy app`, and `make check` all clean. Per V1 milestone-commit policy this work is **uncommitted** on `main` and will squash into the M3 commit after M3.7: **Done**.
- M3.6 — Embedder + asyncio ingest worker + in-process task registry. New `app/core/task_registry.py` exposing `TaskRegistry` and a module-level `TASK_REGISTRY` (dict keyed by string ID; auto-prunes via done-callback that's anchored to the specific task object so overwrites are safe). New `app/ingestion/embedder.py` exposing `embed_texts(texts, *, session) -> list[list[float]]` over `langchain_openai.OpenAIEmbeddings` with hardcoded model `text-embedding-3-small` (1536-dim) and `EMBEDDING_BATCH_SIZE = 64`; resolves the API key via `SettingsService.get_provider_key("openai")` (NOT directly from `OPENAI_API_KEY`) so production behavior matches the user's Settings page; raises `ValueError` if no key configured and `RuntimeError` on dim mismatch with `Settings.embedding_dim`. New `app/ingestion/worker.py` exposing `async run_ingest(document_id)` — owns its own `AsyncSessionLocal()` sessions (do NOT pass one in; runs as a background task long after the originating request closed its session) and drives the document through `pending → parsing → embedding → ready` (or `→ failed`). State-machine deviation from the original spec: the `DocumentStatus` enum (M3.2) has no `chunking` and no `indexed` members, so chunking is collapsed into the `parsing` status and terminal-success is `ready`; chunks are persisted in a single transaction after embedding. Catches all exceptions, marks the row `failed` with a short `Document.error`, and returns normally (so the wrapping task completes cleanly without an "exception was never retrieved" warning); `asyncio.CancelledError` IS re-raised after marking the row failed. `POST /documents` now schedules `run_ingest(doc.id)` via `asyncio.create_task` and registers it under `f"ingest:{doc.id}"`; the 201 response shape is unchanged (status still `pending` at response time). New `tests/integration/conftest.py` autouse fixture drains any leaked `ingest:*` tasks at end of test (with a 2s grace then cancel) so existing M3.3 tests — which upload PDFs without an OpenAI key configured and would now leave a background ingest racing toward `failed` — don't bleed into the next test. New unit suite `tests/unit/test_task_registry.py` (6 tests: register-and-get, cancel-running, cancel-unknown, completed-auto-removed, overwrite-existing, singleton-exists). New integration test `tests/integration/test_ingest_pipeline.py` posts the M3.4 fixture PDF, polls every 500ms (cap 120s for first-run Docling weights), and asserts terminal `ready` with ≥1 chunk, embedding non-null, dim 1536, embedding_model `text-embedding-3-small`; gated behind both `pytest.mark.integration` and `pytest.mark.skipif(not OPENAI_API_KEY)`. Registered the `integration` marker in `pyproject.toml` (alongside the existing `slow` marker). 31/31 unit tests pass; 33 integration tests pass + the new ingest test SKIPS without a key. `ruff`, `ruff format`, `mypy app`, and `alembic check` all clean. **Live-OpenAI integration test was NOT executed** in this session because no `OPENAI_API_KEY` was available in the dev env; manual repro: `cd backend && OPENAI_API_KEY=sk-... uv run pytest tests/integration/test_ingest_pipeline.py -v -s`. Per V1 milestone-commit policy this work is **uncommitted** on `main` and will squash into the M3 commit after M3.7: **Done**.

## Milestone status

- **M1:** Completed and committed.
- **M2:** Completed and committed (`a54515e` + frontend M2.7 at `a98957c`).
- **M3:** Completed and committed as milestone squash (`7f4b8ca`).
- **M4 (partial):** M4.1-M4.4 provider abstraction + adapters completed;
  M4.7 diagnostics endpoint + settings UI test button completed;
  M4.5/M4.6 deferred until run-scoped Evidence/Run tables are in place (M5).

## Current progress (latest)

- Added `app.agents.tools.providers` with:
  - `base.py` (`SearchResult`, `SearchProvider` protocol)
  - `tavily.py`, `exa.py`, `perplexity.py` adapters
- Added `GET /health/search?q=...` in `app/api/health.py`:
  resolves active search provider from settings, validates provider key,
  dispatches one provider call, returns `{ "titles": [..top3..] }`.
- Frontend settings page now has **Test search** button wired to
  `frontend/lib/api.ts::testSearchProvider` and shows returned titles via toast.
- Added tests and fixtures:
  - `tests/unit/test_search_provider_base.py`
  - `tests/unit/test_tavily_provider.py`
  - `tests/unit/test_exa_provider.py`
  - `tests/unit/test_perplexity_provider.py`
  - `tests/integration/test_health_search.py`
  - `tests/fixtures/{tavily_response,exa_response,perplexity_response}.json`

## Deferred work

- **M4.5 / M4.6 tool-level evidence registration** depends on run-scoped
  persistence (`Run` + `Evidence`) that lands with M5 DB/schema work.
  We intentionally deferred this wiring to avoid a temporary nullable/placeholder
  `run_id` design that would require extra cleanup migrations.

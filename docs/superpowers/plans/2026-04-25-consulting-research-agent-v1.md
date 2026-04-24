# Consulting Research Agent V1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **User directive:** This plan is intentionally low-code. Each task lists files, contracts, exact commands, and acceptance checks; implementation code is left to the executing engineer/subagent. Where a code stub appears, it is to lock a cross-task type so signatures match later tasks.

**Goal:** Deliver an end-to-end Market Entry consulting research run: user picks task → uploads docs → answers framing questionnaire → LangGraph pipeline runs Stage 1/2/3 DeepAgents with Reviewer gates → Synthesis + Audit produce a citation-backed Markdown report streamed live into a Next.js chat UI.

**Architecture:** FastAPI backend (single process, in-process asyncio task runner) drives a LangGraph `StateGraph` whose research stages are DeepAgents and whose framing/reviewer/synthesis/audit nodes are plain LangChain LLM calls with structured output. State is checkpointed to Postgres; documents are ingested via Docling into pgvector; events stream to a Next.js + TS frontend via SSE.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x async, Alembic, LangGraph, DeepAgents, LangChain (provider-native), Pydantic v2, Docling, pgvector, Postgres 16, Tavily/Exa/Perplexity SDKs, Next.js 14 (App Router), TypeScript, TailwindCSS, shadcn/ui, Playwright, Docker Compose.

**Source spec:** `docs/superpowers/specs/2026-04-25-consulting-research-agent-design.md`

---

## File Structure

A single monorepo. Files are sized to one clear responsibility.

### Backend (`backend/`)

- `app/main.py` — FastAPI app factory, lifespan, router mounting.
- `app/core/config.py` — `Settings` (pydantic-settings) for env (DB URL, Fernet key, default provider).
- `app/core/db.py` — async SQLAlchemy engine + session factory.
- `app/core/crypto.py` — Fernet wrap/unwrap helpers.
- `app/core/events.py` — event publish helper (insert into `events` table) + Postgres LISTEN/NOTIFY hook for SSE wakeup.
- `app/core/sse.py` — SSE response helper (tails `events` for a `run_id` from `Last-Event-ID`).
- `app/core/budget.py` — per-run usage accumulator (token + cost), reads `core/pricing.py`.
- `app/core/pricing.py` — static `(provider, model) → $/1M tokens` table.
- `app/core/task_registry.py` — in-process `dict[run_id, asyncio.Task]` with `cancel(run_id)`.
- `app/models/__init__.py` — re-exports.
- `app/models/{user,settings_kv,provider_key,task_type,document,chunk,run,message,event,artifact,evidence,gate}.py` — one ORM class per file.
- `app/schemas/{settings,documents,runs,events,gates,evidence,framing}.py` — Pydantic DTOs.
- `app/api/{tasks,documents,settings,runs}.py` — routers; thin handlers, all logic in services.
- `app/services/{settings_service,document_service,run_service,framing_service}.py` — business logic.
- `app/agents/llm.py` — `PROVIDER_REGISTRY` + `get_chat_model(role)` + `get_embeddings()`.
- `app/agents/tools/__init__.py` — exports a `build_tools(run_id)` factory binding tools to a run.
- `app/agents/tools/web_search.py` — provider-agnostic LangChain `@tool`.
- `app/agents/tools/providers/{tavily,exa,perplexity}.py` — adapters implementing `SearchProvider`.
- `app/agents/tools/providers/base.py` — `SearchProvider` Protocol + `SearchResult` model.
- `app/agents/tools/fetch_url.py` — HTTP fetch + readability cleanup.
- `app/agents/tools/rag_search.py` — pgvector cosine similarity tool.
- `app/agents/tools/read_doc.py` — returns full Docling markdown for a doc.
- `app/agents/tools/artifacts.py` — `write_artifact(path, content)` tool, upserts `artifacts` row.
- `app/agents/tools/cite.py` — `cite_source` helper used by tools to register evidence and return `src_id`.
- `app/agents/market_entry/state.py` — `RunState` TypedDict + sub-models (`FramingBrief`, `GateVerdict`, `EvidenceRef`).
- `app/agents/market_entry/graph.py` — assembles the LangGraph `StateGraph` with conditional edges.
- `app/agents/market_entry/nodes/framing.py` — Framing LangGraph node.
- `app/agents/market_entry/nodes/reviewer.py` — Reviewer node (parametrized by stage slug).
- `app/agents/market_entry/nodes/synthesis.py` — Synthesis node.
- `app/agents/market_entry/nodes/audit.py` — Audit node.
- `app/agents/market_entry/deepagents/stage1_foundation.py` — DeepAgent with `market_sizing`, `customer`, `regulatory` sub-agents.
- `app/agents/market_entry/deepagents/stage2_competitive.py` — DeepAgent with `competitor`, `channel`, `pricing` sub-agents.
- `app/agents/market_entry/deepagents/stage3_risk.py` — DeepAgent with `risk` sub-agent only.
- `app/agents/market_entry/prompts/*.md` — externalized system prompts per node/sub-agent.
- `app/ingestion/docling_parser.py` — Docling wrapper; returns markdown + metadata.
- `app/ingestion/chunker.py` — token-aware splitter (target 800, overlap 100).
- `app/ingestion/embedder.py` — wraps LangChain Embeddings.
- `app/workers/run_worker.py` — `run_pipeline(run_id)` async entrypoint that invokes the LangGraph.
- `app/workers/ingest_worker.py` — `ingest_document(doc_id)` async entrypoint.
- `app/testing/fake_chat_model.py` — `FakeChatModel(BaseChatModel)` for deterministic tests.
- `alembic/versions/*.py` — schema migrations, one per logical change.
- `tests/{unit,integration,e2e}/...` — mirror `app/` layout.
- `pyproject.toml`, `alembic.ini`, `.env.example`.

### Frontend (`frontend/`)

- `app/layout.tsx`, `app/page.tsx` — task picker + new-run entrypoint.
- `app/runs/[id]/page.tsx` — 4-pane run view.
- `app/settings/page.tsx` — provider + key + retry-cap config.
- `components/TaskTypeCard.tsx`, `components/DocUploader.tsx`, `components/QuestionnaireForm.tsx`.
- `components/ChatStream.tsx` — SSE consumer hook + transcript renderer.
- `components/AgentTrace.tsx` — collapsible stage/agent/tool tree.
- `components/ReportView.tsx` — markdown renderer with `[^src_id]` chip extraction.
- `components/SourcesSidebar.tsx` — evidence list + bidirectional linking.
- `components/UsagePanel.tsx` — tokens/cost/cancel.
- `lib/api.ts` — typed REST client.
- `lib/sse.ts` — `useEventStream(runId)` hook with `Last-Event-ID` reconnect.
- `lib/types.ts` — DTOs mirroring backend schemas.

### Infra (`infra/`)

- `docker-compose.yml` — postgres (pgvector image), backend, frontend.
- `postgres/init.sql` — `CREATE EXTENSION IF NOT EXISTS vector;`
- `Makefile` (root) — `make dev`, `make test`, `make lint`, `make migrate`.

---

## Conventions

- **Commits:** Conventional Commits (`feat:`, `fix:`, `chore:`, `test:`, `refactor:`). One commit per completed task.
- **Branch:** Work on `master` for V1 (single dev). Push only when explicitly asked.
- **TDD:** Every backend task writes the failing test first, runs it, implements, re-runs.
- **Linting:** `ruff check`, `ruff format`, `mypy app` for backend; `pnpm lint`, `pnpm typecheck` for frontend. CI tasks added in M1.
- **Migrations:** Every schema change gets its own Alembic revision; never edit a previous revision.
- **Secrets:** Never commit `.env`. Only `.env.example`.

---

# Milestone M1 — Skeleton

**Outcome:** `make dev` brings up Postgres + FastAPI + Next.js. Health endpoints respond. Alembic baseline exists. Lint + test commands run green.

### Task M1.1 — Initialize backend project

**Files:** Create `backend/pyproject.toml`, `backend/.env.example`, `backend/app/__init__.py`, `backend/app/main.py`, `backend/app/core/config.py`, `backend/tests/__init__.py`, `backend/tests/test_health.py`.

- [ ] **Step 1:** Initialize project with `uv init backend --package` and add deps: `fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pydantic`, `pydantic-settings`, `cryptography`, `httpx`. Dev deps: `pytest`, `pytest-asyncio`, `pytest-cov`, `httpx`, `ruff`, `mypy`, `types-passlib`.
- [ ] **Step 2:** Write failing test `tests/test_health.py::test_health_returns_ok` that uses `httpx.AsyncClient(app=app)` to GET `/health` and expect `{"status": "ok"}`.
- [ ] **Step 3:** Run: `uv run pytest tests/test_health.py -v` — expect failure (route missing).
- [ ] **Step 4:** Implement `Settings` in `core/config.py` (env vars: `DATABASE_URL`, `FERNET_KEY`, `APP_ENV`); implement `app/main.py` `create_app()` with `/health` returning `{"status": "ok", "env": settings.app_env}`.
- [ ] **Step 5:** Re-run pytest — expect PASS.
- [ ] **Step 6:** Add `ruff.toml` (line-length 100, target-version py312) and `mypy.ini` (strict, ignore tests). Run `uv run ruff check . && uv run mypy app` — fix until clean.
- [ ] **Step 7:** Commit: `chore(backend): scaffold FastAPI app with health endpoint`.

### Task M1.2 — Initialize frontend project

**Files:** Create `frontend/` via `pnpm create next-app`.

- [ ] **Step 1:** Run `pnpm create next-app@latest frontend --typescript --app --tailwind --eslint --src-dir=false --import-alias "@/*"`. Accept defaults otherwise.
- [ ] **Step 2:** Install shadcn: `cd frontend && pnpm dlx shadcn@latest init -d` then add `button card input textarea sonner` components.
- [ ] **Step 3:** Replace `app/page.tsx` body with a temporary heading `Consulting Research Agent` and a card showing build info.
- [ ] **Step 4:** Run `pnpm dev` and `curl localhost:3000` returns HTML containing the heading.
- [ ] **Step 5:** Add `pnpm typecheck` script (`tsc --noEmit`). Run `pnpm lint && pnpm typecheck` — clean.
- [ ] **Step 6:** Commit: `chore(frontend): scaffold Next.js app with Tailwind + shadcn`.

### Task M1.3 — Postgres + pgvector via Docker Compose

**Files:** Create `infra/docker-compose.yml`, `infra/postgres/init.sql`, root `Makefile`, root `.env.example`.

- [ ] **Step 1:** `docker-compose.yml` defines a single `postgres` service using `pgvector/pgvector:pg16`, env `POSTGRES_DB=consulting`, `POSTGRES_USER=consulting`, `POSTGRES_PASSWORD=consulting`, port 5432, volume `pgdata:/var/lib/postgresql/data`, mounts `./postgres/init.sql:/docker-entrypoint-initdb.d/01-init.sql`.
- [ ] **Step 2:** `init.sql` contains `CREATE EXTENSION IF NOT EXISTS vector;`.
- [ ] **Step 3:** Root `Makefile` targets: `db-up` (`docker compose -f infra/docker-compose.yml up -d postgres`), `db-down`, `db-logs`, `dev` (db-up + backend + frontend in background).
- [ ] **Step 4:** Run `make db-up`, then `docker exec -it consulting_agents-postgres-1 psql -U consulting -d consulting -c '\dx'` and confirm `vector` extension is listed.
- [ ] **Step 5:** Commit: `chore(infra): add postgres+pgvector docker-compose`.

### Task M1.4 — Async DB session + Alembic baseline

**Files:** Create `backend/app/core/db.py`, `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/versions/0001_baseline.py`.

- [ ] **Step 1:** Write failing test `tests/test_db.py::test_db_session_can_select_one` that opens a session and runs `SELECT 1`. Run — expect import-error / connect-failure.
- [ ] **Step 2:** Implement `core/db.py`: `engine = create_async_engine(settings.database_url)`, `AsyncSessionLocal`, `get_session()` dependency.
- [ ] **Step 3:** `alembic init -t async alembic` from `backend/`. Edit `alembic/env.py` to use `settings.database_url` (sync mode by swapping `+asyncpg` → empty driver) and import `Base` (placeholder for now).
- [ ] **Step 4:** Generate baseline: `alembic revision -m "baseline"`. Leave `upgrade()` empty.
- [ ] **Step 5:** Run `alembic upgrade head` against the docker DB. Verify `alembic_version` table exists.
- [ ] **Step 6:** Run the test — expect PASS.
- [ ] **Step 7:** Add Makefile target `migrate` (`cd backend && uv run alembic upgrade head`).
- [ ] **Step 8:** Commit: `chore(backend): add async SQLAlchemy + Alembic baseline`.

### Task M1.5 — Pre-commit + CI script

**Files:** Create `.pre-commit-config.yaml`, root `scripts/check.sh`.

- [ ] **Step 1:** Pre-commit hooks: `ruff`, `ruff-format`, `mypy` (backend); `prettier`, `eslint` (frontend, via `pnpm`).
- [ ] **Step 2:** `scripts/check.sh` runs both backend and frontend lint + typecheck + tests; non-zero exit on any failure.
- [ ] **Step 3:** Run `bash scripts/check.sh` — expect green.
- [ ] **Step 4:** Commit: `chore: add pre-commit and check.sh`.

---

# Milestone M2 — Settings, Encrypted Keys, LLM Provider Layer

**Outcome:** A user can store provider API keys (encrypted) and per-role model overrides via REST. A backend `ping` endpoint instantiates the configured chat model and returns its echo.

### Task M2.1 — `users` and `settings_kv` tables

**Files:** Create `backend/app/models/user.py`, `backend/app/models/settings_kv.py`, `backend/alembic/versions/0002_users_and_settings.py`.

- [ ] **Step 1:** Failing test `tests/integration/test_settings_kv.py::test_upsert_and_read_setting` that opens a session, upserts `("max_stage_retries", {"value": 2})`, and reads it back.
- [ ] **Step 2:** Implement ORM: `User(id uuid pk, created_at)` (single seeded row id `00000000-0000-0000-0000-000000000001`); `SettingKV(user_id fk, key text, value jsonb, primary_key=(user_id,key))`.
- [ ] **Step 3:** Alembic revision creates tables. Seed the singleton user via SQL in `upgrade()`.
- [ ] **Step 4:** Run `alembic upgrade head` and the test — expect PASS.
- [ ] **Step 5:** Commit: `feat(db): add users and settings_kv tables`.

### Task M2.2 — Fernet crypto helper

**Files:** Create `backend/app/core/crypto.py`, `backend/tests/unit/test_crypto.py`.

- [ ] **Step 1:** Failing tests: `test_wrap_then_unwrap_roundtrips`, `test_unwrap_with_wrong_key_raises`.
- [ ] **Step 2:** Implement `wrap(plaintext: str) -> str` and `unwrap(ciphertext: str) -> str` using `cryptography.fernet.Fernet`, key from `settings.fernet_key`.
- [ ] **Step 3:** Run tests — expect PASS.
- [ ] **Step 4:** Commit: `feat(core): add Fernet wrap/unwrap helper`.

### Task M2.3 — `provider_keys` table + service

**Files:** Create `backend/app/models/provider_key.py`, `backend/app/services/settings_service.py`, `backend/alembic/versions/0003_provider_keys.py`, `backend/tests/integration/test_settings_service.py`.

- [ ] **Step 1:** Failing tests: `test_set_provider_key_stores_encrypted`, `test_get_provider_key_returns_plaintext`, `test_overwrite_provider_key_replaces_value`.
- [ ] **Step 2:** ORM: `ProviderKey(id, user_id fk, provider str, encrypted_key str, created_at, updated_at)`, unique on `(user_id, provider)`.
- [ ] **Step 3:** Alembic revision.
- [ ] **Step 4:** `SettingsService.set_provider_key(provider, key)` and `.get_provider_key(provider) -> str | None` using `crypto.wrap/unwrap`.
- [ ] **Step 5:** Run tests + assert the DB column never contains the plaintext.
- [ ] **Step 6:** Commit: `feat(settings): encrypted provider key storage`.

### Task M2.4 — Settings REST API

**Files:** Create `backend/app/schemas/settings.py`, `backend/app/api/settings.py`, `backend/tests/integration/test_settings_api.py`.

- [ ] **Step 1:** Failing tests via httpx `AsyncClient`: GET returns providers list with `has_key:bool` flags but never raw keys; PUT `/settings/providers/{provider}` stores key; PUT `/settings/model_overrides` stores role→{provider,model} map; PUT `/settings/search_provider` selects active provider; PUT `/settings/max_stage_retries` accepts integer 1..5.
- [ ] **Step 2:** Implement schemas (Pydantic) and router. Mount in `main.py`.
- [ ] **Step 3:** Run tests — expect PASS.
- [ ] **Step 4:** Commit: `feat(api): settings endpoints`.

### Task M2.5 — LangChain provider registry

**Files:** Create `backend/app/agents/llm.py`, `backend/tests/unit/test_llm_registry.py`.

- [ ] **Step 1:** Add deps: `langchain-core`, `langchain-anthropic`, `langchain-openai`, `langchain-google-genai`, `langchain-aws`, `langchain-ollama`.
- [ ] **Step 2:** Failing test: `test_get_chat_model_for_unknown_role_falls_back_to_default`, `test_get_chat_model_uses_role_override`, `test_get_chat_model_raises_when_provider_key_missing`.
- [ ] **Step 3:** Implement `PROVIDER_REGISTRY: dict[str, Callable[[str, dict], BaseChatModel]]` mapping `"anthropic" → ChatAnthropic`, etc. Implement `get_chat_model(role: str, *, session) -> BaseChatModel` that:
  - reads `model_overrides[role]` from settings (falls back to env default),
  - reads `provider_keys[provider]` (raises `MissingProviderKey` if absent),
  - constructs the chat model with explicit `api_key=...` (never via env),
  - applies `with_retry(stop_after_attempt=3, wait_exponential_jitter=True)`.
- [ ] **Step 4:** Same for `get_embeddings(session) -> Embeddings` (mirror per active embedding provider).
- [ ] **Step 5:** Run tests with monkeypatched provider classes — expect PASS.
- [ ] **Step 6:** Commit: `feat(agents): LangChain provider registry`.

### Task M2.6 — `/health/llm` ping endpoint

**Files:** Modify `backend/app/api/settings.py` (or new `app/api/health.py`), `backend/tests/integration/test_llm_ping.py`.

- [ ] **Step 1:** Failing test: GET `/health/llm?role=framing` returns `{"ok": true, "provider": "...", "model": "...", "echo": "...string from model..."}` when keys are set; returns 412 (Precondition Failed) with a clear error if not.
- [ ] **Step 2:** Implement endpoint that calls `get_chat_model("framing").invoke([HumanMessage("Reply with the word 'pong'.")]).content`.
- [ ] **Step 3:** Run integration test against a real provider only when `RUN_LIVE_LLM=1`; otherwise use a monkeypatched `BaseChatModel`.
- [ ] **Step 4:** Commit: `feat(api): /health/llm ping endpoint`.

### Task M2.7 — Settings UI

**Files:** Create `frontend/app/settings/page.tsx`, `frontend/lib/api.ts`, `frontend/lib/types.ts`.

- [ ] **Step 1:** `lib/api.ts` exports typed `getProviders()`, `setProviderKey(provider, key)`, `setModelOverride(role, provider, model)`, `setSearchProvider(provider)`, `setMaxStageRetries(n)`, `pingLLM(role)`.
- [ ] **Step 2:** `app/settings/page.tsx` renders three sections: (a) LLM providers (per-role select + "set key" inputs that POST individually), (b) Search provider radio (Tavily/Exa/Perplexity) + key input, (c) Global max retries number input (1..5).
- [ ] **Step 3:** "Test connection" button per role calls `pingLLM(role)` and toasts result.
- [ ] **Step 4:** Manual smoke: open `/settings`, set a key, verify GET reveals `has_key:true`, click test → toast.
- [ ] **Step 5:** Commit: `feat(frontend): settings page for providers and keys`.

---

# Milestone M3 — Document Ingestion + RAG Tool

**Outcome:** A user can upload a PDF; an asyncio worker parses with Docling, chunks, embeds, and stores; `rag_search` tool returns top-k relevant chunks for a query.

### Task M3.1 — `tasks_catalog` table seeded with Market Entry

**Files:** Create `backend/app/models/task_type.py`, `backend/app/api/tasks.py`, `backend/alembic/versions/0004_task_catalog.py`, `backend/tests/integration/test_tasks_catalog.py`.

- [ ] **Step 1:** Failing test: GET `/tasks` returns `[{slug:"market_entry", name:"Market Entry", enabled:true}, {slug:"ma", name:"M&A", enabled:false}]`.
- [ ] **Step 2:** ORM `TaskType(slug pk, name, description, enabled)`. Migration seeds both rows.
- [ ] **Step 3:** Implement router; mount.
- [ ] **Step 4:** Run test — PASS. Commit: `feat(api): task catalog with market_entry and ma stubs`.

### Task M3.2 — `documents` and `chunks` tables

**Files:** Create `backend/app/models/document.py`, `backend/app/models/chunk.py`, `backend/alembic/versions/0005_documents_and_chunks.py`.

- [ ] **Step 1:** ORM:
  - `Document(id uuid pk, user_id fk, filename, mime, size, status enum[pending,parsing,embedding,ready,failed], error text|null, created_at, updated_at)`.
  - `Chunk(id uuid pk, document_id fk, ord int, text text, embedding vector(N), embedding_model text, metadata jsonb)`.
- [ ] **Step 2:** Migration creates tables and HNSW index on `chunks.embedding` (`USING hnsw (embedding vector_cosine_ops)`). Vector dim `N` is taken from a new setting `embedding_dim` (default 1536) — read inside the migration via env var `EMBEDDING_DIM` to keep it pure SQL.
- [ ] **Step 3:** Failing test `tests/integration/test_documents_orm.py::test_insert_document_and_chunk_roundtrip` inserts a document + a chunk with a random vector and reads it back.
- [ ] **Step 4:** Run migration + test — PASS.
- [ ] **Step 5:** Commit: `feat(db): documents and chunks with pgvector HNSW`.

### Task M3.3 — Document upload API (no ingest yet)

**Files:** Create `backend/app/schemas/documents.py`, `backend/app/services/document_service.py`, `backend/app/api/documents.py`, `backend/tests/integration/test_documents_api.py`.

- [ ] **Step 1:** Failing tests: POST `/documents` (multipart) creates row with `status=pending` and writes binary to `data/uploads/{doc_id}`; GET `/documents` lists; DELETE removes row + file.
- [ ] **Step 2:** Implement service writing to a configurable `UPLOAD_DIR` and router.
- [ ] **Step 3:** Run tests — PASS. Commit: `feat(api): document upload + list + delete`.

### Task M3.4 — Docling parser wrapper

**Files:** Create `backend/app/ingestion/docling_parser.py`, `backend/tests/unit/test_docling_parser.py`, fixture `backend/tests/fixtures/sample.pdf` (a 2-page PDF).

- [ ] **Step 1:** Add `docling` dep.
- [ ] **Step 2:** Failing test: `parse_to_markdown(path)` returns `(markdown:str, metadata:dict)` where markdown contains text from the PDF and `metadata['page_count'] == 2`.
- [ ] **Step 3:** Implement using `DocumentConverter().convert(path)`. Keep the function synchronous; it'll run in a thread executor.
- [ ] **Step 4:** Run — PASS. Commit: `feat(ingestion): docling parser wrapper`.

### Task M3.5 — Token-aware chunker

**Files:** Create `backend/app/ingestion/chunker.py`, `backend/tests/unit/test_chunker.py`.

- [ ] **Step 1:** Add `tiktoken` dep.
- [ ] **Step 2:** Failing tests: `test_chunk_short_text_returns_single_chunk`, `test_chunk_long_text_respects_target_size`, `test_chunks_overlap_by_configured_amount`, `test_chunks_preserve_order`.
- [ ] **Step 3:** Implement `chunk(markdown: str, target_tokens=800, overlap_tokens=100) -> list[ChunkPayload]` (`ChunkPayload(ord:int, text:str)`).
- [ ] **Step 4:** Run — PASS. Commit: `feat(ingestion): token-aware chunker`.

### Task M3.6 — Embedder + ingest worker

**Files:** Create `backend/app/ingestion/embedder.py`, `backend/app/workers/ingest_worker.py`, `backend/app/core/task_registry.py`, `backend/tests/integration/test_ingest_worker.py`.

- [ ] **Step 1:** Failing test: scheduling `ingest_document(doc_id)` against the sample PDF transitions status `pending → parsing → embedding → ready` and creates ≥1 chunk row with non-null embedding.
- [ ] **Step 2:** Implement `embedder.embed_texts(texts) -> list[list[float]]` via `get_embeddings()`.
- [ ] **Step 3:** Implement `task_registry.spawn(run_id|doc_id, coro)` storing the `asyncio.Task` and removing it on done; expose `cancel(key)`.
- [ ] **Step 4:** Implement `ingest_worker.ingest_document(doc_id)`: load doc → run Docling in `asyncio.to_thread` → chunk → embed → bulk insert chunks → set status `ready` (or `failed` with error on exception).
- [ ] **Step 5:** Wire into upload API: after creating row, `task_registry.spawn(doc_id, ingest_document(doc_id))`.
- [ ] **Step 6:** Run integration test (uses fake embeddings provider returning fixed vectors) — PASS.
- [ ] **Step 7:** Commit: `feat(ingestion): asyncio ingest worker pipeline`.

### Task M3.7 — `rag_search` LangChain tool

**Files:** Create `backend/app/agents/tools/rag_search.py`, `backend/app/agents/tools/cite.py`, `backend/app/models/evidence.py`, `backend/alembic/versions/0006_evidence_table.py`, `backend/tests/integration/test_rag_search_tool.py`.

- [ ] **Step 1:** ORM `Evidence(id uuid pk, run_id fk, src_id text, kind enum[web,doc], url text|null, chunk_id fk|null, title text, snippet text, accessed_at, provider text)`. Unique on `(run_id, src_id)`.
- [ ] **Step 2:** `cite.register_evidence(session, run_id, *, kind, url|chunk_id, title, snippet, provider) -> str` returns a stable `src_id` (e.g., `src_<8-hex>` from a content hash); idempotent.
- [ ] **Step 3:** Failing test for tool: invoking `rag_search(query, doc_ids?)` with a fake run finds the seeded chunk, returns `[{src_id, title, snippet}]`, and writes an `Evidence` row.
- [ ] **Step 4:** Implement `rag_search` as a LangChain `@tool` produced by a factory `build_rag_search(run_id, session_factory)`. Internally embeds the query and runs `chunks.embedding <=> :q ORDER BY ... LIMIT k`.
- [ ] **Step 5:** Commit: `feat(agents): rag_search tool with evidence registration`.

---

# Milestone M4 — Web Search Abstraction

**Outcome:** A single `web_search` tool dispatches to Tavily, Exa, or Perplexity based on the active setting; results auto-register as evidence; UI provider selector works end-to-end.

### Task M4.1 — `SearchProvider` Protocol + result schema

**Files:** Create `backend/app/agents/tools/providers/base.py`, `backend/tests/unit/test_search_provider_base.py`.

- [ ] **Step 1:** Define `SearchResult(BaseModel)` with `title, url, snippet, published_at|None, source` and `class SearchProvider(Protocol): async def search(query, k) -> list[SearchResult]`.
- [ ] **Step 2:** Trivial test asserts the model serializes/deserializes round-trip.
- [ ] **Step 3:** Commit: `feat(tools): search provider protocol`.

### Task M4.2 — Tavily adapter

**Files:** Create `backend/app/agents/tools/providers/tavily.py`, `backend/tests/unit/test_tavily_provider.py`, `backend/tests/fixtures/tavily_response.json`.

- [ ] **Step 1:** Add `tavily-python` (or use `httpx` direct).
- [ ] **Step 2:** Failing test using `respx` to mock the HTTP call returns 3 normalized `SearchResult`s.
- [ ] **Step 3:** Implement `TavilyProvider(api_key)` using `httpx.AsyncClient`.
- [ ] **Step 4:** Commit: `feat(tools): tavily search provider`.

### Task M4.3 — Exa adapter

**Files:** Create `backend/app/agents/tools/providers/exa.py`, `backend/tests/unit/test_exa_provider.py`, fixture.

- [ ] **Step 1:** Same shape as M4.2 against Exa's `/search` endpoint.
- [ ] **Step 2:** Commit: `feat(tools): exa search provider`.

### Task M4.4 — Perplexity adapter

**Files:** Create `backend/app/agents/tools/providers/perplexity.py`, test, fixture.

- [ ] **Step 1:** Same shape against Perplexity's `chat/completions` (use the `pplx-online` model, parse citations into results).
- [ ] **Step 2:** Commit: `feat(tools): perplexity search provider`.

### Task M4.5 — `web_search` LangChain tool

**Files:** Create `backend/app/agents/tools/web_search.py`, `backend/app/agents/tools/__init__.py`, `backend/tests/integration/test_web_search_tool.py`.

- [ ] **Step 1:** Failing test: configure search provider = `tavily` with mocked HTTP; invoke the tool; assert it returns results with `src_id`s and writes corresponding `Evidence` rows.
- [ ] **Step 2:** Implement `build_web_search(run_id, session_factory)` factory producing the `@tool` that:
  - reads active provider from settings,
  - looks up provider key (raise tool error if missing — DeepAgent will record gap),
  - constructs the right adapter,
  - registers each result via `cite.register_evidence`,
  - returns `[{src_id, title, snippet, url}]`.
- [ ] **Step 3:** Implement `tools/__init__.py::build_tools(run_id, session_factory) -> list[BaseTool]` returning `[web_search, fetch_url (next task), rag_search, read_doc, write_artifact]`.
- [ ] **Step 4:** Commit: `feat(tools): provider-agnostic web_search`.

### Task M4.6 — `fetch_url` and `read_doc` tools

**Files:** Create `backend/app/agents/tools/fetch_url.py`, `backend/app/agents/tools/read_doc.py`, tests.

- [ ] **Step 1:** Failing test for `fetch_url`: against `respx`-mocked URL, returns cleaned text snippet and registers evidence.
- [ ] **Step 2:** Implement using `httpx` + `readability-lxml` (add dep).
- [ ] **Step 3:** Failing test for `read_doc`: returns the markdown for a `ready` document.
- [ ] **Step 4:** Implement.
- [ ] **Step 5:** Commit: `feat(tools): fetch_url and read_doc`.

### Task M4.7 — Settings UI: search provider selector

**Files:** Modify `frontend/app/settings/page.tsx`.

- [ ] **Step 1:** Add radio group binding to `setSearchProvider`. Per-provider key field. "Test search" button calls a new `/health/search?q=test` endpoint (add it: returns top-3 titles).
- [ ] **Step 2:** Manual smoke: select Tavily, set key, test → toast with titles.
- [ ] **Step 3:** Commit: `feat(frontend): search provider selector + test`.

---

# Milestone M5 — LangGraph Harness, Run Lifecycle, SSE

**Outcome:** A minimal 2-node LangGraph (`framing` → `done`) executes inside an asyncio task. The run lifecycle is persisted; SSE streams events to the chat UI; one DeepAgent stage node is proven to embed inside the graph.

### Task M5.1 — `runs`, `messages`, `events`, `artifacts`, `gates` tables

**Files:** Create `backend/app/models/{run,message,event,artifact,gate}.py`, `backend/alembic/versions/0007_runs_messages_events.py`.

- [ ] **Step 1:** ORM:
  - `Run(id uuid, user_id, task_id fk, goal text, status enum[created,questioning,running,cancelling,cancelled,completed,failed], created_at, updated_at, model_snapshot jsonb)`.
  - `Message(id, run_id, role enum[user,system,assistant], content text, created_at)`.
  - `Event(id bigserial, run_id, ts, agent text|null, type text, payload jsonb)`. Index on `(run_id, id)`.
  - `Artifact(id, run_id, path text, kind text, content text, updated_at)`. Unique `(run_id, path)`.
  - `Gate(id, run_id, stage text, attempt int, verdict text, gaps jsonb, target_agents jsonb, rationale text, created_at)`.
- [ ] **Step 2:** Migration. Test: insert one row of each.
- [ ] **Step 3:** Commit: `feat(db): runs/messages/events/artifacts/gates`.

### Task M5.2 — Event publisher with LISTEN/NOTIFY

**Files:** Create `backend/app/core/events.py`, `backend/tests/integration/test_events_publish.py`.

- [ ] **Step 1:** Failing test: `publish(run_id, type, payload, agent=None)` inserts row AND fires `NOTIFY events_run_<run_id>`.
- [ ] **Step 2:** Implement using `asyncpg.connection.execute("NOTIFY ...")`. Provide `subscribe(run_id) -> AsyncIterator[Event]` that uses LISTEN + replays older events when given a `last_event_id`.
- [ ] **Step 3:** Commit: `feat(core): event publisher with LISTEN/NOTIFY`.

### Task M5.3 — SSE response helper + `/runs/{id}/stream`

**Files:** Create `backend/app/core/sse.py`, `backend/app/api/runs.py`, `backend/tests/integration/test_sse_stream.py`.

- [ ] **Step 1:** Failing test: open SSE connection to `/runs/{id}/stream`, publish 3 events from another task, assert client receives them in order and each has an `id:` field.
- [ ] **Step 2:** Implement SSE helper that yields events from `subscribe(run_id, last_event_id=request.headers.get("Last-Event-ID"))`.
- [ ] **Step 3:** Add reconnect test: close connection, publish more events, reopen with `Last-Event-ID`, assert only newer events arrive.
- [ ] **Step 4:** Commit: `feat(api): SSE stream endpoint with Last-Event-ID resume`.

### Task M5.4 — `RunState` and graph skeleton

**Files:** Create `backend/app/agents/market_entry/state.py`, `backend/app/agents/market_entry/graph.py`, `backend/tests/unit/test_graph_skeleton.py`.

- [ ] **Step 1:** Define in `state.py` (this stub locks types):

```python
from typing import TypedDict, NotRequired

class FramingBrief(TypedDict):
    objective: str
    target_market: str
    constraints: list[str]
    questionnaire_answers: dict[str, str]

class GateVerdict(TypedDict):
    verdict: str          # "advance" | "reiterate"
    stage: str
    attempt: int
    gaps: list[str]
    target_agents: list[str]
    rationale: str

class EvidenceRef(TypedDict):
    src_id: str
    title: str
    url: NotRequired[str]

class RunState(TypedDict, total=False):
    run_id: str
    goal: str
    document_ids: list[str]
    framing: FramingBrief
    artifacts: dict[str, str]
    evidence: list[EvidenceRef]
    stage_attempts: dict[str, int]
    gate_verdicts: dict[str, GateVerdict]
    target_agents: list[str] | None
    cancelled: bool
```

- [ ] **Step 2:** `graph.py::build_graph()` returns a compiled LangGraph with two nodes: `framing_stub` (sets `state["framing"] = {...}`), `done` (terminal). Edge `framing_stub → done`. Use the `langgraph.checkpoint.postgres` checkpointer.
- [ ] **Step 3:** Failing test: invoke compiled graph with `{"run_id": "...", "goal": "..."}` and assert final state contains `framing`.
- [ ] **Step 4:** Commit: `feat(graph): RunState and skeleton StateGraph`.

### Task M5.5 — Run service + asyncio run worker

**Files:** Create `backend/app/services/run_service.py`, `backend/app/workers/run_worker.py`, `backend/app/schemas/runs.py`, `backend/tests/integration/test_run_lifecycle.py`.

- [ ] **Step 1:** Failing test: POST `/runs` with `{task_type:"market_entry", goal:"X", document_ids:[]}` returns `{run_id}`, status becomes `questioning`, and an `artifact_update` event for `framing/questionnaire.json` arrives via SSE within 3s.
- [ ] **Step 2:** Implement POST `/runs` handler:
  - validates task is enabled,
  - creates `Run` row with status `questioning` and `model_snapshot` of current settings,
  - spawns `run_worker.start_framing(run_id)` via `task_registry`,
  - returns `{run_id}`.
- [ ] **Step 3:** Implement `run_worker.start_framing(run_id)`: invokes the graph up to and including the `framing` node, persists the questionnaire artifact, publishes `artifact_update` event.
- [ ] **Step 4:** Implement POST `/runs/{id}/answers`: stores answers in a Message, sets status `running`, spawns `run_worker.continue_after_framing(run_id, answers)`.
- [ ] **Step 5:** Implement POST `/runs/{id}/cancel`: sets `cancelling`, calls `task_registry.cancel(run_id)`, publishes `cancel_ack`.
- [ ] **Step 6:** GET `/runs/{id}` returns metadata + artifact list. GET `/runs/{id}/artifacts/{path}` returns content.
- [ ] **Step 7:** Run all tests — PASS.
- [ ] **Step 8:** Commit: `feat(runs): full lifecycle with asyncio worker and SSE`.

### Task M5.6 — Embed one DeepAgent node in the graph (proof-of-concept)

**Files:** Modify `backend/app/agents/market_entry/graph.py`, create `backend/app/agents/market_entry/deepagents/_smoke.py`, `backend/tests/integration/test_deepagent_node.py`.

- [ ] **Step 1:** Add `deepagents` dep.
- [ ] **Step 2:** `_smoke.py::build_smoke_deepagent(tools, model)` returns a minimal `create_deep_agent(...)` configured with one sub-agent `echo` that writes `"hello from deepagent"` to a file `smoke.md` via `write_artifact`.
- [ ] **Step 3:** Add a third node `smoke_deepagent` to the graph between `framing_stub` and `done`.
- [ ] **Step 4:** Failing test: drive the graph end-to-end (with `FakeChatModel` returning the scripted tool calls), assert `artifacts["smoke.md"] == "hello from deepagent"`.
- [ ] **Step 5:** Commit: `feat(graph): proof-of-concept DeepAgent node embedded in StateGraph`.

### Task M5.7 — Frontend: New Run + minimal Run view

**Files:** Modify `frontend/app/page.tsx`, create `frontend/app/runs/[id]/page.tsx`, `frontend/lib/sse.ts`, `frontend/components/ChatStream.tsx`.

- [ ] **Step 1:** `app/page.tsx`: task picker (only Market Entry enabled), goal textarea, "Start" button → POST `/runs`, navigate to `/runs/{id}`.
- [ ] **Step 2:** `lib/sse.ts::useEventStream(runId)` hook with native `EventSource`, persists last seen `id` in `useRef` and rebuilds the connection on disconnect.
- [ ] **Step 3:** `runs/[id]/page.tsx`: renders a single column streaming the event log as JSON cards (placeholder; AgentTrace replaces it in M7).
- [ ] **Step 4:** Manual smoke: start a run, watch events arrive in real time.
- [ ] **Step 5:** Commit: `feat(frontend): minimal new-run + live event stream`.

---

# Milestone M6 — Market Entry Pipeline

**Outcome:** Full Market Entry pipeline runs end-to-end: Framing questionnaire → Stage 1 (3 sub-agents) → Reviewer gate → Stage 2 → Reviewer → Stage 3 → Reviewer → Synthesis → Audit. Citation enforcement works. Final report renders.

### Task M6.1 — Externalize prompts

**Files:** Create `backend/app/agents/market_entry/prompts/{framing,reviewer,synthesis,audit,stage1_foundation,stage2_competitive,stage3_risk}.md` and `backend/app/agents/market_entry/prompts/__init__.py` exposing `load(name) -> str`.

- [ ] **Step 1:** Each `.md` file holds the full system prompt. Drafting guidelines per file:
  - **framing.md:** consulting-engagement-manager voice; instructs the model to produce a JSON `FramingBrief` and a `questionnaire` (list of `{id, label, type:text|select|multiselect, options?, helper, required}`) covering: target geography/segment, success criteria, time horizon, budget, risk tolerance, prior assumptions, known competitors, regulatory hot-spots, channel preferences. Output schema enforced via `with_structured_output`.
  - **reviewer.md:** strict-critic voice; consumes the just-completed stage's artifacts + framing brief; emits `GateVerdict` JSON only. Decision criteria: every key claim cited, all stage objectives addressed, no obvious contradictions, evidence freshness reasonable.
  - **synthesis.md:** McKinsey-style executive-summary voice; produces `final_report.md` per the section list in spec §7.4.
  - **audit.md:** consumes `final_report.md`; emits `audit.md` with weak claims, contradictions, residual gaps. Does not modify the report.
  - **stage1_foundation.md / stage2_competitive.md / stage3_risk.md:** DeepAgent supervisor instructions describing each sub-agent's mandate, required output (markdown section + trailing JSON metadata block), citation rules, and tool usage order (`rag_search` → `web_search` → `fetch_url`).
- [ ] **Step 2:** Unit test: `load("framing")` returns non-empty string; assert presence of key tokens (`"questionnaire"`, `"FramingBrief"`).
- [ ] **Step 3:** Commit: `feat(prompts): externalize all market_entry prompts`.

### Task M6.2 — Framing node with structured output

**Files:** Create `backend/app/agents/market_entry/nodes/framing.py`, `backend/app/schemas/framing.py`, `backend/tests/integration/test_framing_node.py`.

- [ ] **Step 1:** `schemas/framing.py` defines `Questionnaire(items: list[QuestionItem])` and `QuestionItem` with the fields above.
- [ ] **Step 2:** Failing test (with `FakeChatModel` scripted): node invocation yields a state update with `framing.brief_draft` and writes `framing/questionnaire.json` artifact + emits `artifact_update` event.
- [ ] **Step 3:** Implement node: `model = get_chat_model("framing").with_structured_output(FramingResponse)` where `FramingResponse = {brief: FramingBriefDraft, questionnaire: Questionnaire}`. After invocation, write artifact via `write_artifact` tool (called directly, not by the model).
- [ ] **Step 4:** Commit: `feat(graph): framing node with structured questionnaire output`.

### Task M6.3 — Questionnaire form in frontend

**Files:** Create `frontend/components/QuestionnaireForm.tsx`, modify `frontend/app/runs/[id]/page.tsx`.

- [ ] **Step 1:** When event `artifact_update` for `framing/questionnaire.json` arrives, fetch via REST and render `QuestionnaireForm` with controlled inputs per question type.
- [ ] **Step 2:** "Submit answers" → POST `/runs/{id}/answers`. Hide form, show "Pipeline running…" placeholder.
- [ ] **Step 3:** Manual smoke against the live framing node.
- [ ] **Step 4:** Commit: `feat(frontend): questionnaire form rendering and submission`.

### Task M6.4 — Reviewer node (parametrized by stage)

**Files:** Create `backend/app/agents/market_entry/nodes/reviewer.py`, `backend/tests/unit/test_reviewer_node.py`.

- [ ] **Step 1:** `make_reviewer_node(stage_slug)` returns a callable `(state) -> partial RunState update`. Reads all artifacts under `f"stage_{stage_slug}/"`, calls `get_chat_model("reviewer").with_structured_output(GateVerdict)`, writes Gate row, publishes `gate_verdict` event, returns `{"gate_verdicts": {stage_slug: verdict}, "stage_attempts": {...incremented...}}`.
- [ ] **Step 2:** Failing test (FakeChatModel): on `advance` verdict, returns advance; on `reiterate` with `target_agents=["customer"]`, returns state with `target_agents` set.
- [ ] **Step 3:** Commit: `feat(graph): reviewer node with structured GateVerdict output`.

### Task M6.5 — Stage 1 Foundation DeepAgent node

**Files:** Create `backend/app/agents/market_entry/deepagents/stage1_foundation.py`, `backend/tests/integration/test_stage1_node.py`.

- [ ] **Step 1:** `build_stage1_node(session_factory)` returns an async callable used as a LangGraph node. Internally:
  - constructs `tools = build_tools(run_id, session_factory)`,
  - constructs `create_deep_agent(model=get_chat_model("research"), tools=tools, instructions=load("stage1_foundation"), subagents=[market_sizing, customer, regulatory])`,
  - inputs include the framing brief and (on retry) `state["target_agents"]` and prior reviewer gaps,
  - after agent finishes, walks artifacts under `stage_1_foundation/` and updates `state["artifacts"]`.
- [ ] **Step 2:** Each sub-agent is a small dict `{"name": "...", "description": "...", "prompt": "...", "tools": [...]}` consumed by DeepAgents. Sub-agent prompts come from a sub-folder `prompts/stage1/{market_sizing,customer,regulatory}.md`.
- [ ] **Step 3:** Failing integration test (FakeChatModel scripted): driving the node yields three artifacts (`stage_1_foundation/market_sizing.md`, `customer.md`, `regulatory.md`) each containing at least one `[^src_id]` token corresponding to a registered Evidence row.
- [ ] **Step 4:** Commit: `feat(stage1): foundation DeepAgent node with 3 sub-agents`.

### Task M6.6 — Stage 2 Competitive DeepAgent node

**Files:** Create `backend/app/agents/market_entry/deepagents/stage2_competitive.py`, `backend/app/agents/market_entry/prompts/stage2/{competitor,channel,pricing}.md`, test.

- [ ] **Step 1:** Mirror M6.5 with sub-agents `competitor`, `channel`, `pricing`. Stage 2 instructions include reading Stage 1 artifacts (passed via initial message context).
- [ ] **Step 2:** Test: artifacts produced under `stage_2_competitive/`; sub-agents reference Stage 1 sources where appropriate.
- [ ] **Step 3:** Commit: `feat(stage2): competitive DeepAgent node`.

### Task M6.7 — Stage 3 Risk DeepAgent node

**Files:** Create `backend/app/agents/market_entry/deepagents/stage3_risk.py`, `backend/app/agents/market_entry/prompts/stage3/risk.md`, test.

- [ ] **Step 1:** Single sub-agent `risk`. Reads Stage 1 + 2 artifacts.
- [ ] **Step 2:** Commit: `feat(stage3): risk DeepAgent node`.

### Task M6.8 — Synthesis node

**Files:** Create `backend/app/agents/market_entry/nodes/synthesis.py`, test.

- [ ] **Step 1:** Reads all stage artifacts and framing brief; calls `get_chat_model("synthesis")`; produces `final_report.md`. Replaces `[^src_id]` tokens through (no transformation, but validates each id exists in `Evidence`); appends a `## Sources` section auto-generated from referenced evidence rows in the order they appear.
- [ ] **Step 2:** Failing test: when artifact contains `[^src_unknown]`, raises `CitationError` (caught by graph and routed to a `node_failed` handler — see M6.10).
- [ ] **Step 3:** Commit: `feat(graph): synthesis node with citation validation`.

### Task M6.9 — Audit node

**Files:** Create `backend/app/agents/market_entry/nodes/audit.py`, test.

- [ ] **Step 1:** Reads `final_report.md` + accumulated `gate_verdicts`; emits `audit.md` listing weak claims, contradictions, and residual gaps. Sets `Run.status = completed` after writing.
- [ ] **Step 2:** Commit: `feat(graph): audit node`.

### Task M6.10 — Wire the full graph with conditional edges

**Files:** Modify `backend/app/agents/market_entry/graph.py`, create `backend/app/agents/market_entry/edges.py`, `backend/tests/integration/test_full_pipeline_smoke.py`.

- [ ] **Step 1:** Edge layout:
  - `START → framing → (await user answers — handled by run_worker)`
  - `(after answers) → stage1 → reviewer1 → conditional(stage1)`
  - `conditional(stage1)`: `advance → stage2`; `reiterate AND attempt < max_retries → stage1 (with target_agents)`; else `stage2 (forced advance)`
  - same pattern for stage2/3
  - `… → synthesis → audit → END`
  - `node_failed` edge: any node raising → `audit` with a partial-report flag
- [ ] **Step 2:** `edges.py::route_after_reviewer(stage_slug)` returns the conditional function used by `add_conditional_edges`.
- [ ] **Step 3:** Failing end-to-end smoke test using `FakeChatModel` whose responses script: framing → stage1 (cited) → reviewer advance → stage2 (cited) → reviewer reiterate once with `target_agents=["pricing"]` → stage2 again with only pricing rerun → reviewer advance → stage3 → reviewer advance → synthesis → audit. Assert: 3 stage2 attempts captured, only `pricing` rerun on retry, final report contains all expected sections, evidence count > 0, run status `completed`.
- [ ] **Step 4:** Commit: `feat(graph): full Market Entry pipeline with conditional gates`.

### Task M6.11 — Run worker drives full graph after answers

**Files:** Modify `backend/app/workers/run_worker.py`.

- [ ] **Step 1:** Replace the placeholder `continue_after_framing` with one that resumes the LangGraph from the framing checkpoint, injecting answers, and runs to completion. Periodically checks `Run.status == cancelling` between nodes via the LangGraph stream API; on cancel, persists current state and exits cleanly.
- [ ] **Step 2:** Integration test: start run, submit answers, observe `run_complete` event with status `completed`.
- [ ] **Step 3:** Cancel test: start run, submit answers, send cancel mid-stage, expect `cancel_ack` and final status `cancelled`.
- [ ] **Step 4:** Commit: `feat(runs): worker drives full graph with cancel support`.

---

# Milestone M7 — Polish (UX, Trace, Sources Sidebar, Cost, README)

**Outcome:** The 4-pane Run view shows live AgentTrace, ReportView with citation chips, SourcesSidebar with bidirectional linking, and UsagePanel with running token/cost + Cancel. README has setup + screenshots.

### Task M7.1 — Per-call token/cost tracking

**Files:** Create `backend/app/core/pricing.py`, modify `backend/app/agents/llm.py`, `backend/app/core/budget.py`, `backend/tests/unit/test_budget.py`.

- [ ] **Step 1:** `pricing.py` exports `PRICES: dict[(provider, model), {input: float, output: float}]` ($/1M tokens). Cover the 4-5 default models used in V1.
- [ ] **Step 2:** Attach a `UsageMetadataCallbackHandler` to every chat model returned by `get_chat_model()`. The handler calls `core.events.publish(run_id, "usage_update", {...})` keyed off a context var holding current `run_id`.
- [ ] **Step 3:** `core.budget.RunUsage(run_id)` accumulates and exposes `to_dict() -> {input_tokens, output_tokens, est_cost_usd}`.
- [ ] **Step 4:** Tests with monkeypatched usage events.
- [ ] **Step 5:** Commit: `feat(core): per-run token + cost tracking`.

### Task M7.2 — AgentTrace component

**Files:** Create `frontend/components/AgentTrace.tsx`, modify run page.

- [ ] **Step 1:** Consumes the SSE event stream; groups events into `Stage > Agent > ToolCalls` collapsible tree. Each tool call shows query/url and result count.
- [ ] **Step 2:** Verdicts (`gate_verdict`) shown as colored banners per stage (green advance, amber reiterate, red forced-advance).
- [ ] **Step 3:** Component test using a synthetic event array.
- [ ] **Step 4:** Commit: `feat(frontend): AgentTrace component`.

### Task M7.3 — ReportView with citation chips

**Files:** Create `frontend/components/ReportView.tsx`.

- [ ] **Step 1:** Renders markdown via `react-markdown` + `remark-gfm`; custom transform replaces `[^src_id]` tokens with clickable `<button data-src-id>` chips.
- [ ] **Step 2:** Component test: renders sample report and finds N chip buttons.
- [ ] **Step 3:** Listens for `artifact_update` events for `final_report.md` (and stage artifacts before synthesis) to live-update.
- [ ] **Step 4:** Commit: `feat(frontend): ReportView with citation chips`.

### Task M7.4 — SourcesSidebar with bidirectional linking

**Files:** Create `frontend/components/SourcesSidebar.tsx`, modify `lib/api.ts` to fetch evidence list.

- [ ] **Step 1:** Backend: add `GET /runs/{id}/evidence` returning all `Evidence` rows.
- [ ] **Step 2:** Sidebar renders a scrollable list of cards (title, snippet, url with favicon, accessed-at, provider).
- [ ] **Step 3:** Bidirectional linking: clicking a chip in `ReportView` highlights matching sidebar card and scrolls it into view; clicking a sidebar card highlights all matching chips in the report.
- [ ] **Step 4:** Component tests for selection state.
- [ ] **Step 5:** Commit: `feat(frontend): SourcesSidebar with citation linking`.

### Task M7.5 — UsagePanel + Cancel

**Files:** Create `frontend/components/UsagePanel.tsx`.

- [ ] **Step 1:** Shows running totals from `usage_update` events. "Cancel run" button calls POST `/runs/{id}/cancel` and disables itself once status is terminal.
- [ ] **Step 2:** Manual smoke: start a run, watch tokens climb, cancel mid-run, expect status cancelled.
- [ ] **Step 3:** Commit: `feat(frontend): UsagePanel with cancel button`.

### Task M7.6 — Run view 4-pane layout assembly

**Files:** Modify `frontend/app/runs/[id]/page.tsx`.

- [ ] **Step 1:** Layout: left ChatStream, center-left AgentTrace, center-right ReportView, right SourcesSidebar, top-right floating UsagePanel. Use CSS grid with min-widths and a horizontal scroll container on small screens.
- [ ] **Step 2:** Add a "Download report" button visible after `run_complete`.
- [ ] **Step 3:** Commit: `feat(frontend): assemble 4-pane run view`.

### Task M7.7 — README, screenshots, .env.example consolidation

**Files:** Create root `README.md`, capture 3 screenshots into `docs/screenshots/`.

- [ ] **Step 1:** README sections: Overview, Architecture diagram (link to spec), Quick Start (`make dev` + first-run settings walkthrough), Configuration, Running tests, Roadmap (M&A in V2).
- [ ] **Step 2:** Capture screenshots: Settings page, Questionnaire, Run view mid-pipeline.
- [ ] **Step 3:** Consolidate `.env.example` files into a single root one, referenced from `make dev`.
- [ ] **Step 4:** Commit: `docs: README + screenshots + consolidated .env.example`.

---

# Milestone M8 — V2 Stub (M&A skeleton)

**Outcome:** Selecting M&A in the UI no longer says "coming soon" — it runs a placeholder LangGraph that produces a stub report explaining V1 limits. Provides extension scaffolding for V2.

### Task M8.1 — M&A skeleton graph

**Files:** Create `backend/app/agents/ma/graph.py`, `backend/app/agents/ma/state.py`, `backend/app/agents/ma/prompts/placeholder.md`, modify `task_type` seed to enable `ma`.

- [ ] **Step 1:** Single-node graph that writes `final_report.md` with a one-paragraph "M&A pipeline coming in V2" message and immediately completes.
- [ ] **Step 2:** Run service dispatches to `ma.graph.build_graph()` when `task_type == "ma"`.
- [ ] **Step 3:** Smoke test: start an M&A run, no questionnaire, run completes immediately with the stub report.
- [ ] **Step 4:** Commit: `feat(ma): V2 skeleton graph and routing`.

---

# Cross-Cutting Concerns & Acceptance Criteria

### Definition of Done (whole V1)

- All M1–M8 tasks committed with tests green.
- `make dev` brings up the full app on a clean machine in < 5 minutes (after `docker pull`).
- A new user can: open `/settings`, configure Anthropic + Tavily keys, return to `/`, start a Market Entry run on a real goal with one uploaded PDF, complete the questionnaire, and obtain a Markdown report with at least 5 cited sources within 10 minutes (depending on model).
- Cancel button reliably stops a run within 30 seconds.
- Reconnecting to the SSE stream (e.g., refresh) replays missed events with no gaps.
- `bash scripts/check.sh` exits 0.

### Test Coverage Targets

- Backend overall ≥ 70% line coverage; critical paths (LLM router, tools, graph edges, citation validation) ≥ 90%.
- One end-to-end smoke test (M6.10) executes the entire pipeline against `FakeChatModel`.

### What is explicitly NOT in V1 (deferred to V2)

- M&A real pipeline.
- Profitability / Pricing / Operations consulting types.
- LightRAG, Neo4j, hybrid retrieval.
- PPTX/DOCX/PDF export.
- Multi-user auth, RBAC.
- Hard token/cost/time caps.
- Mid-run human-in-the-loop pauses beyond the upfront questionnaire.
- Auto-resume of crashed runs (checkpoint exists; manual resume button comes in V2).

---

# Self-Review Checklist (filled out by plan author)

**1. Spec coverage:**

| Spec section | Implementing task(s) |
|---|---|
| §2 Scope (Market Entry only, MD-only export) | M3.1, M5–M7, M7.6 (download) |
| §3 Locked decisions | All milestones |
| §6.1 LLM provider layer | M2.5, M2.6 |
| §6.2 Web search abstraction | M4.1–M4.5 |
| §6.3 Tools layer | M3.7, M4.5, M4.6 |
| §6.4 Hybrid orchestration (LangGraph + DeepAgents) | M5.4, M5.6, M6.5–M6.10 |
| §6.5 RAG ingestion | M3.2–M3.7 |
| §6.6 Run lifecycle | M5.1, M5.5, M6.11 |
| §6.7 Persistence + checkpoints | M2.1, M2.3, M3.2, M3.7, M5.1, M5.4 (checkpointer) |
| §6.8 SSE streaming | M5.2, M5.3, M5.7 |
| §6.9 Soft guardrails | M7.1, M7.5 |
| §7 Market Entry pipeline (stages/gates/sub-agents) | M6.1–M6.10 |
| §8 Frontend flows | M1.2, M2.7, M4.7, M5.7, M6.3, M7.2–M7.6 |
| §9 API surface | M2.4, M3.1, M3.3, M5.3, M5.5, M7.4 |
| §10 Error handling | M2.5 (retry/fallback), M6.8 (citation), M6.10 (node_failed edge) |
| §11 Testing strategy | Tests inline in every task; M6.10 = end-to-end smoke |
| §12 Infra | M1.3, M1.4, M7.7 |
| §13 Milestones | This plan = M1..M8 |
| §14 Resolved decisions (no Redis, sources sidebar, configurable retry cap, etc.) | M3.6 (no Redis), M2.4 (max_stage_retries), M6.4 (uses setting), M7.4 (sidebar) |

No gaps identified.

**2. Placeholder scan:** none — every task has files, contracts, commands, and tests.

**3. Type consistency:** `RunState`, `FramingBrief`, `GateVerdict`, `EvidenceRef`, `Evidence`, `Run`, `Artifact`, `Gate` names match between M5.4, M5.1, M3.7, M6.4, M6.5–M6.10. `register_evidence` signature consistent between M3.7 and consumers in M4.5/M4.6. `build_tools(run_id, session_factory)` consistent in M4.5 and M6.5–M6.7.

# Consulting Research Agent — V1 Design Spec

**Date:** 2026-04-25
**Status:** Draft for review
**Owner:** abhishek

---

## 1. Purpose

Build an open-source, agentic consulting research system that compresses consulting-style research from months into days. The system does not replace consultants. It automates problem framing, evidence gathering, multi-angle analysis, critique, and draft generation, so a human can review and decide.

The product feels like a chatbot: the user picks a consulting task type, optionally uploads documents, states a goal, answers an upfront questionnaire, and receives a structured, citation-backed Markdown report.

V1 ships a **single end-to-end vertical slice**: the **Market Entry** consulting task. M&A and other task types are scaffolded (registered in the catalog, supervisor stubbed) but not implemented.

---

## 2. Scope

### In scope (V1)

- Web chat UI to start, monitor, and review one Market Entry run.
- FastAPI backend with deepagents-based orchestration.
- Single local user. Encrypted server-side storage of LLM and search-provider API keys.
- Pluggable web search across **Tavily, Exa, Perplexity** behind one tool interface.
- Pluggable LLM access via **LiteLLM** router (provider/model configurable per agent role).
- Document ingestion via **Docling** → chunk → embed → **Postgres + pgvector**.
- Staged Market Entry pipeline with **Reviewer quality gates** between stages and bounded re-iteration.
- Mandatory inline citations with an auto-tracked per-run evidence table.
- Soft cost/usage warnings and a manual cancel control.
- Live agent trace and live-updating Markdown report via **Server-Sent Events**.
- Local Docker Compose dev environment.

### Out of scope (V1)

- M&A and other consulting types (registered, not implemented).
- LightRAG and Neo4j graph reasoning.
- PPTX / DOCX / PDF export (Markdown only; download supported).
- Multi-user auth, RBAC, team workspaces.
- Hard token / cost / time budgets that auto-stop a run.
- Mid-run human-in-the-loop pauses (clarification is one-shot upfront only).
- Hybrid retrieval (BM25 + vector); V1 is vector-only.
- Mobile-optimized UI.

---

## 3. Locked Decisions (from brainstorming)

| Topic | Decision |
|---|---|
| V1 scope | Thin vertical slice — Market Entry only |
| Knowledge layer | Docling + Postgres + pgvector. No Neo4j, no LightRAG in V1 |
| Web search | Provider-agnostic interface; Tavily, Exa, Perplexity adapters; user picks in Settings |
| LLM | LiteLLM router; provider/model configurable per agent role |
| Repo | Monorepo: `/backend` (FastAPI), `/frontend` (Next.js + TS), `/infra` |
| Streaming | SSE; runs persisted in Postgres; reconnect via `Last-Event-ID` |
| Users | Single local user, no login |
| API keys | Server-side, encrypted at rest with Fernet (key from env) |
| Clarification UX | **One-shot upfront questionnaire** (no mid-run pauses) |
| Sub-agent execution | **Staged waves with Reviewer quality gates**, max 2 retries per stage |
| Citations | **Mandatory inline citations**, auto-tracked evidence table, reviewer-enforced |
| Guardrails | **Soft warnings + manual cancel only** in V1 (no hard caps) |

---

## 4. High-Level Architecture

```
┌──────────────────────────┐          REST + SSE          ┌──────────────────────────────┐
│ Next.js Chat UI          │ ───────────────────────────▶ │ FastAPI                      │
│ • Task picker            │                              │ • /tasks /documents /runs   │
│ • Questionnaire form     │ ◀──── stream events ──────── │ • /runs/{id}/stream (SSE)    │
│ • Live agent trace       │                              │ • /settings/providers        │
│ • Live report viewer     │                              └──────────┬───────────────────┘
└──────────────────────────┘                                         │
                                                                     ▼
                                                ┌──────────────────────────────────────┐
                                                │ Orchestrator (deepagents)            │
                                                │  Market Entry Supervisor             │
                                                │   ├ Stage 0  Framing (questionnaire) │
                                                │   ├ Stage 1  Foundation              │
                                                │   │   (sizing | customer | reg)      │
                                                │   ├ Gate 1   Reviewer                │
                                                │   ├ Stage 2  Competitive             │
                                                │   │   (competitor | channel | price) │
                                                │   ├ Gate 2   Reviewer                │
                                                │   ├ Stage 3  Risk                    │
                                                │   ├ Gate 3   Reviewer                │
                                                │   ├ Stage 4  Synthesis               │
                                                │   └ Final    Audit                   │
                                                └──────────┬───────────────────────────┘
                                                           │
                            ┌──────────────────────────────┼─────────────────────────────┐
                            ▼                              ▼                             ▼
                   ┌────────────────────┐       ┌─────────────────────┐       ┌──────────────────────┐
                   │ Tools layer        │       │ LiteLLM router      │       │ Postgres + pgvector  │
                   │ • web_search       │       │ Anthropic / OpenAI  │       │ runs, events,        │
                   │   ├ tavily         │       │ Gemini / Bedrock /  │       │ messages, artifacts, │
                   │   ├ exa            │       │ local               │       │ documents, chunks,   │
                   │   └ perplexity     │       └─────────────────────┘       │ evidence, settings   │
                   │ • fetch_url        │                                     └──────────────────────┘
                   │ • rag_search       │                ▲
                   │ • read_doc         │                │
                   │ • write_artifact   │       ┌─────────────────────┐
                   │ • cite_source      │       │ Docling worker      │
                   └────────────────────┘       │ parse → chunk →     │
                                                │ embed → upsert      │
                                                └─────────────────────┘
```

---

## 5. Repo Layout

```
consulting_agents/
├── backend/
│   ├── app/
│   │   ├── main.py                       # FastAPI entrypoint
│   │   ├── api/
│   │   │   ├── tasks.py                  # GET /tasks
│   │   │   ├── documents.py              # POST/GET/DELETE /documents
│   │   │   ├── runs.py                   # POST /runs, GET /runs/{id}, /stream, cancel
│   │   │   └── settings.py               # provider + key management
│   │   ├── core/
│   │   │   ├── config.py                 # pydantic-settings
│   │   │   ├── db.py                     # async SQLAlchemy
│   │   │   ├── crypto.py                 # Fernet wrap/unwrap
│   │   │   ├── events.py                 # event bus → SSE
│   │   │   └── budget.py                 # token/cost counter (soft warnings)
│   │   ├── models/                       # SQLAlchemy ORM
│   │   ├── schemas/                      # Pydantic DTOs
│   │   ├── agents/
│   │   │   ├── base.py
│   │   │   ├── llm.py                    # LiteLLM model factory (per-role)
│   │   │   ├── tools/
│   │   │   │   ├── web_search.py
│   │   │   │   ├── providers/{tavily,exa,perplexity}.py
│   │   │   │   ├── fetch_url.py
│   │   │   │   ├── rag_search.py
│   │   │   │   ├── read_doc.py
│   │   │   │   ├── artifacts.py
│   │   │   │   └── cite.py               # records evidence, returns src_id
│   │   │   ├── market_entry/
│   │   │   │   ├── supervisor.py         # deepagents top-level
│   │   │   │   ├── framing.py
│   │   │   │   ├── stage1_foundation/{market_sizing,customer,regulatory}.py
│   │   │   │   ├── stage2_competitive/{competitor,channel,pricing}.py
│   │   │   │   ├── stage3_risk/risk.py
│   │   │   │   ├── reviewer.py           # gate; emits JSON verdict
│   │   │   │   ├── synthesis.py
│   │   │   │   └── audit.py
│   │   │   └── ma/                       # stub for V2
│   │   ├── ingestion/
│   │   │   ├── docling_parser.py
│   │   │   ├── chunker.py
│   │   │   └── embedder.py               # via LiteLLM embeddings
│   │   └── workers/
│   │       ├── ingest_worker.py          # arq job: parse+chunk+embed
│   │       └── run_worker.py             # arq job: executes a run
│   ├── alembic/
│   ├── tests/
│   └── pyproject.toml
├── frontend/
│   ├── app/
│   │   ├── page.tsx                      # task picker / new run
│   │   ├── runs/[id]/page.tsx            # chat + trace + report
│   │   └── settings/page.tsx             # providers + keys
│   ├── components/
│   │   ├── TaskTypeCard.tsx
│   │   ├── DocUploader.tsx
│   │   ├── QuestionnaireForm.tsx
│   │   ├── ChatStream.tsx                # SSE consumer
│   │   ├── AgentTrace.tsx
│   │   ├── ReportView.tsx                # MD render + citation hover
│   │   └── UsagePanel.tsx                # tokens / cost / cancel
│   ├── lib/api.ts
│   └── package.json
├── infra/
│   ├── docker-compose.yml
│   ├── postgres/init.sql                 # CREATE EXTENSION vector
│   └── README.md
├── docs/superpowers/specs/
├── .env.example
└── README.md
```

---

## 6. Backend Components

### 6.1 LLM router (LiteLLM)

`agents/llm.py` exposes `get_chat_model(role: str)` returning a LangChain-compatible chat model via LiteLLM. Mapping of `role → provider/model` lives in `settings.model_overrides` (DB) with an env-level default. Suggested defaults:

| Role | Default model |
|---|---|
| framing, reviewer, audit | mid-tier reasoning model |
| sub-agents (research) | mid-tier with tool use |
| synthesis | top-tier reasoning model |
| embeddings | `text-embedding-3-small` (or provider equivalent) |

### 6.2 Web search abstraction

```python
class SearchProvider(Protocol):
    async def search(self, query: str, k: int = 8) -> list[SearchResult]: ...

class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    published_at: datetime | None
    source: str           # provider name
```

Implementations: `TavilyProvider`, `ExaProvider`, `PerplexityProvider`. The `web_search` tool reads the active provider + key from the `settings` table per request and dispatches.

### 6.3 Tools layer

All tools share two responsibilities: do the work, and emit structured events.

| Tool | Purpose |
|---|---|
| `web_search(query, k?)` | Provider-agnostic search; auto-registers each result into the run's evidence table and returns `src_id`s |
| `fetch_url(url)` | Fetches and cleans page content; auto-registers as evidence |
| `rag_search(query, doc_ids?)` | Vector search over uploaded docs; auto-registers chunk as evidence |
| `read_doc(doc_id)` | Returns full Docling-parsed Markdown for a document |
| `cite_source(src_id, claim)` | Optional explicit citation registration (used by sub-agents that synthesize across sources) |
| `write_artifact(path, content)` | Writes/updates a Markdown artifact for the run (e.g., `stage1/market_sizing.md`, `final_report.md`) |
| `write_todos(...)` | deepagents built-in; supervisor uses for staged plan |

Every tool emits a `tool_call` and `tool_result` event into the run event stream.

### 6.4 Deepagents orchestration

The Market Entry **Supervisor** is a deepagents `create_deep_agent(...)` configured with:

- **Subagents:** framing, reviewer, market_sizing, customer, regulatory, competitor, channel, pricing, risk, synthesis, audit.
- **Tools:** the layer above plus deepagents built-ins (`write_todos`, virtual filesystem).
- **System prompt:** encodes the staged pipeline (see §7), forbids advancing past a gate without a Reviewer `advance` verdict, requires inline citations.

### 6.5 RAG ingestion pipeline

1. `POST /documents` accepts file upload, stores binary under `/data/uploads/{doc_id}`, inserts a `documents` row with `status='pending'`.
2. arq job picks it up: Docling → structured Markdown → token-aware chunker (target ~800 tokens, 100 overlap) → LiteLLM embedding → `chunks(embedding vector(1536))`.
3. `documents.status` transitions `pending → parsing → embedding → ready` (or `failed` with error).
4. `rag_search(query, doc_ids?)` performs cosine similarity (`<=>`) with optional filter by document scope.

### 6.6 Run lifecycle

States: `created → questioning → running → cancelling → cancelled | completed | failed`.

1. `POST /runs` with `{task_type, goal, document_ids[]}` → status `created`.
2. Backend enqueues a short `framing_worker` arq job and returns immediately with status `questioning`. The worker invokes the Framing agent and writes the questionnaire artifact (`framing/questionnaire.json`); UI subscribes to SSE and renders the form once the `artifact_update` event for that path arrives.
3. UI submits answers via `POST /runs/{id}/answers` → enqueues `run_worker` arq job → status `running`.
4. Worker executes the staged pipeline, streaming events through Postgres `events` table; the SSE endpoint tails this table.
5. Manual cancel via `POST /runs/{id}/cancel` sets status `cancelling`; the worker checks between stages and after each tool call, finalizes whatever exists, sets `cancelled`.
6. On completion, `final_report.md` artifact exists, status `completed`.

### 6.7 Persistence (Postgres + pgvector)

Core tables (Alembic-managed):

- `users` (single row in V1; column reserved for future multi-user)
- `provider_keys (id, user_id, provider, encrypted_key, created_at)` — Fernet-encrypted
- `settings (user_id, key, value_json)` — active LLM router config, active search provider, model overrides
- `tasks (id, slug, name, description, enabled)` — catalog
- `documents (id, user_id, filename, mime, size, status, error, created_at)`
- `chunks (id, document_id, ord, text, embedding vector(N), embedding_model text, metadata jsonb)` — `N` is set at first ingest from the active embedding model's dimension and recorded in `settings.embedding_dim`. Switching embedding model requires a re-ingest migration; this is documented in the Settings UI and not handled automatically in V1.
- `runs (id, user_id, task_id, goal, status, created_at, updated_at, model_snapshot jsonb)`
- `messages (id, run_id, role, content, created_at)` — user-facing chat
- `events (id, run_id, ts, agent, type, payload jsonb)` — full agent trace; SSE source of truth
- `artifacts (id, run_id, path, kind, content, updated_at)` — versionless overwrite-on-write Markdown
- `evidence (id, run_id, src_id, kind, url|chunk_id, title, snippet, accessed_at)` — citation registry
- `gates (id, run_id, stage, attempt, verdict, gaps jsonb, target_agents jsonb, created_at)`

Indexes: `chunks` HNSW on `embedding`; `events(run_id, id)` for SSE replay.

### 6.8 SSE streaming

`GET /runs/{id}/stream` returns `text/event-stream`. The handler tails the `events` table by `id > Last-Event-ID`. Event types:

`stage_start`, `stage_complete`, `agent_start`, `agent_complete`, `tool_call`, `tool_result`, `gate_verdict`, `artifact_update`, `usage_update`, `clarification_request` (Stage 0 only), `cancel_ack`, `run_complete`, `error`.

Reconnects resume from `Last-Event-ID`. The events table is the durable log; the SSE handler is a thin tailer.

### 6.9 Soft guardrails

`core/budget.py` accumulates token usage and dollar estimates per run (LiteLLM exposes per-call token + cost). Every `tool_call` emits a `usage_update` event. The UI shows running totals and a Cancel button. No tool ever blocks on budget in V1.

---

## 7. Market Entry Pipeline

### 7.1 Stages and gates

```
Stage 0  Framing               (sync, blocks UI; returns questionnaire)
   │
   ▼ user submits answers
Stage 1  Foundation
   ├─ market_sizing
   ├─ customer
   └─ regulatory               (parallel, asyncio.gather)
   │
   ▼
Gate 1   Reviewer              ──▶ verdict.advance? ──no──▶ retry stage 1 (≤2)
   │ yes                                                       │
   ▼                                                           ▼ retries exhausted → forced advance, gaps logged
Stage 2  Competitive
   ├─ competitor
   ├─ channel
   └─ pricing                  (parallel; reads stage 1 artifacts)
   │
   ▼
Gate 2   Reviewer              ──▶ same retry rule
   │
   ▼
Stage 3  Risk
   │
   ▼
Gate 3   Reviewer              ──▶ same retry rule
   │
   ▼
Stage 4  Synthesis             (recommendation + assumptions)
   │
   ▼
Final    Audit                 (logs residual gaps; never re-iterates)
```

### 7.2 Sub-agent contract

Every research sub-agent must:

1. Read its inputs: framing brief, prior-stage artifacts (if any), reviewer feedback (if a retry).
2. Use `rag_search` first (uploaded docs), then `web_search` + `fetch_url` for external evidence.
3. Produce a Markdown section with **inline citations** of the form `[^src_id]` using `src_id`s returned by tools.
4. Append a short JSON metadata block at the end (front-matter style) containing: `key_findings[]`, `assumptions[]`, `open_questions[]`, `evidence_ids[]`.
5. Write the section via `write_artifact("stage{n}/{agent}.md", ...)`.

### 7.3 Reviewer (gate) contract

The Reviewer is a deepagents subagent invoked after each stage. It reads all artifacts from the just-completed stage and emits a strict JSON verdict (no prose):

```json
{
  "verdict": "advance" | "reiterate",
  "stage": "foundation",
  "attempt": 1,
  "gaps": ["Customer segment X not sized", "..." ],
  "target_agents": ["customer", "market_sizing"],
  "rationale": "1-3 sentences"
}
```

Rules:

- `verdict=reiterate` reruns only `target_agents` (not the whole stage).
- Max 2 reiterations per stage. On the 3rd attempt the supervisor force-advances and logs gaps as residual into `audit`.
- Reviewer cannot ask the user questions; it works only with what is already in the run.

### 7.4 Synthesis and Audit

- **Synthesis** consumes all stage artifacts and the framing brief, produces `final_report.md` with: Executive Summary · Engagement Brief · Market Sizing · Customer & Demand · Competitive Landscape · Regulatory · Channels & Distribution · Pricing & Positioning · Risks · Recommendation · Assumptions & Open Questions · Sources (auto-rendered from the evidence table).
- **Audit** runs once over `final_report.md`, emits an `audit.md` artifact listing weak claims, contradictions, and residual gaps. It does not re-trigger sub-agents in V1.

### 7.5 Citation enforcement

- All claims tagged with `[^src_id]` are validated against the run's `evidence` table. Unknown ids → reviewer flags the section and forces a retry (or, if retries exhausted, audit logs).
- The final report's "Sources" section is generated from `evidence` rows actually referenced in the report.

---

## 8. Frontend Flows

1. **Settings (first-run):** pick LLM provider + key, search provider + key, optional per-role model overrides. Keys POSTed to `/settings/providers` are encrypted at rest.
2. **New Run:** task picker (Market Entry enabled, M&A disabled with "Coming soon"), goal text, optional document uploads (multi-file), submit → `POST /runs`.
3. **Questionnaire:** UI renders the structured questionnaire returned by Framing (fields, types, helper text). Submit → `POST /runs/{id}/answers`, transitions to live view.
4. **Run view (split layout):**
   - **Left:** chat-style transcript (user goal, framing answers, supervisor narration).
   - **Center:** **AgentTrace** — collapsible stage groups, per-agent activity, tool calls with queries and source titles, gate verdicts.
   - **Right:** **ReportView** — live Markdown of `final_report.md` (or the latest stage artifacts before synthesis); citation tokens hover to show source.
   - **Top-right:** **UsagePanel** — running tokens, est. cost, Cancel button.
5. **Completion:** download `final_report.md`. Audit notes shown as a banner.

---

## 9. API Surface (V1)

| Method | Path | Purpose |
|---|---|---|
| GET | `/tasks` | List consulting types (only `market_entry` enabled) |
| GET / PUT | `/settings/providers` | Read / update provider config + keys |
| POST | `/documents` | Upload file (multipart); enqueues ingest |
| GET | `/documents` | List documents with status |
| DELETE | `/documents/{id}` | Delete document + chunks |
| POST | `/runs` | `{task_type, goal, document_ids[]}` → returns `run_id`; questionnaire arrives via SSE `artifact_update` |
| POST | `/runs/{id}/answers` | Submit questionnaire answers; starts pipeline |
| GET | `/runs/{id}` | Run metadata + artifact list |
| GET | `/runs/{id}/stream` | SSE event stream (supports `Last-Event-ID`) |
| GET | `/runs/{id}/artifacts/{path}` | Fetch artifact content |
| POST | `/runs/{id}/cancel` | Soft cancel |

---

## 10. Error Handling

- **Tool errors** (search 5xx, fetch timeout, RAG empty): tool returns a structured error object; agent retries up to 2x with backoff, then proceeds noting the gap.
- **LLM errors** (rate limit, provider outage): LiteLLM retry+fallback if a fallback model is configured; otherwise stage attempt fails and the supervisor logs an `error` event and continues to the next stage with a placeholder gap.
- **Reviewer infinite loops:** prevented by the hard cap of 2 retries per stage.
- **Ingestion failures:** `documents.status='failed'` with error message; surfaced in UI.
- **Worker crash mid-run:** on restart, the worker checks for `runs.status='running'` whose last event is older than N minutes and marks them `failed` (no automatic resume in V1).

---

## 11. Testing Strategy

- **Unit:** chunker, embedder, each search provider adapter (against recorded fixtures), Fernet wrap/unwrap, evidence registration, citation validator.
- **Integration:** ingestion pipeline end-to-end on a small PDF; SSE replay from `Last-Event-ID`.
- **Agent smoke test:** a `FakeChatModel` registered with LiteLLM under provider name `fake` returns scripted JSON/Markdown keyed by agent role and stage attempt. The smoke test drives the supervisor end-to-end, asserting: stage order, gate `advance`/`reiterate` decisions, retry caps (force-advance after 2), citation enforcement (uncited claim → reviewer reiterate), and final report shape (required sections + non-empty Sources).
- **Frontend:** component tests for `AgentTrace`, `ReportView` citation hover, `QuestionnaireForm` validation; one Playwright happy-path against the backend smoke run.

---

## 12. Infra & Dev Experience

- `infra/docker-compose.yml`: `postgres` (with pgvector extension), `redis` (for arq), `backend` (uvicorn), `worker` (arq), `frontend` (next dev).
- `.env.example` covers `DATABASE_URL`, `REDIS_URL`, `FERNET_KEY`, default LLM provider + model, optional default search provider/key.
- `make dev` brings everything up; seeds tasks catalog.
- Pre-commit: ruff + black + mypy (backend); eslint + prettier (frontend).

---

## 13. Milestones

1. **M1 — Skeleton:** monorepo, docker-compose, FastAPI + Next.js hello, Postgres+pgvector, Alembic baseline.
2. **M2 — Settings + LiteLLM:** settings UI, encrypted key storage, ping endpoint.
3. **M3 — Ingestion:** Docling worker, chunk+embed, `rag_search` tool tested.
4. **M4 — Web search:** Tavily/Exa/Perplexity adapters, provider switch in UI.
5. **M5 — Deepagents harness + SSE:** minimal supervisor, run lifecycle persisted, SSE end-to-end in chat UI.
6. **M6 — Market Entry pipeline:** Framing questionnaire, all sub-agents, Reviewer gates, Synthesis, Audit, citation enforcement, final report.
7. **M7 — Polish:** AgentTrace UX, citation hover, report download, usage panel + cancel, README + screenshots.
8. **M8 — V2 stubs:** M&A task type registered with placeholder supervisor.

---

## 14. Open Questions for User Review

1. Is **Markdown-only** export acceptable for V1, or is a basic PDF/print stylesheet required at launch?
2. Are the suggested **default model roles** in §6.1 acceptable, or do you want to pin specific models in the spec?
3. Should the run worker use **arq** (Redis-based, lightweight) as proposed, or do you prefer plain asyncio tasks in V1 (no Redis)?
4. Is the **2-retry** gate cap correct, or should it be configurable per stage from Settings?
5. For the **citation registry**, do you want to display source previews (snippet + accessed-at + favicon) inline on hover, or a dedicated Sources sidebar?

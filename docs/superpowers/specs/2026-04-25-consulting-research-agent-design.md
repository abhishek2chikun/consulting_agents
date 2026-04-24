# Consulting Research Agent — V1 Design Spec

**Date:** 2026-04-25
**Status:** Draft for review
**Owner:** abhishek

---

## 1. Purpose

Build an open-source, agentic consulting research system that compresses consulting-style research from months into days. The system does not replace consultants. It automates problem framing, evidence gathering, multi-angle analysis, critique, and draft generation, so a human can review and decide.

The product feels like a chatbot: the user picks a consulting task type, optionally uploads documents, states a goal, answers an upfront questionnaire, and receives a structured, citation-backed Markdown report.

V1 ships a **single end-to-end vertical slice**: the **Market Entry** consulting task. M&A and other task types are scaffolded (registered in the catalog, graph stubbed) but not implemented.

---

## 2. Scope

### In scope (V1)

- Web chat UI to start, monitor, and review one Market Entry run.
- FastAPI backend with **LangGraph** orchestration as the deterministic outer state machine, and **DeepAgents** wrapped as autonomous research nodes inside specific stages.
- Single local user. Encrypted server-side storage of LLM and search-provider API keys.
- Pluggable web search across **Tavily, Exa, Perplexity** behind one tool interface.
- Pluggable LLM access via **LangChain provider integrations** (`langchain-anthropic`, `langchain-openai`, `langchain-google-genai`, etc.); provider/model configurable per agent role. No LiteLLM.
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
| LLM | LangChain provider integrations (Anthropic, OpenAI, Gemini, Bedrock, etc.); per-role model overrides. **No LiteLLM.** |
| Orchestration | **Hybrid: LangGraph (deterministic outer state machine) + DeepAgents (autonomous research nodes within stages).** |
| Repo | Monorepo: `/backend` (FastAPI), `/frontend` (Next.js + TS), `/infra` |
| Streaming | SSE; runs persisted in Postgres; reconnect via `Last-Event-ID` |
| Users | Single local user, no login |
| API keys | Server-side, encrypted at rest with Fernet (key from env) |
| Clarification UX | **One-shot upfront questionnaire** (no mid-run pauses) |
| Sub-agent execution | **Staged waves with Reviewer quality gates**, retries per stage capped at a single global setting (default 2, configurable in Settings) |
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
                                                │ Orchestrator                         │
                                                │  LangGraph StateGraph (outer)        │
                                                │   ├ Stage 0  Framing  (LLM node)     │
                                                │   ├ Stage 1  Foundation              │
                                                │   │   DeepAgent node                 │
                                                │   │   (sizing | customer | reg)      │
                                                │   ├ Gate 1   Reviewer (LLM node)     │
                                                │   ├ Stage 2  Competitive             │
                                                │   │   DeepAgent node                 │
                                                │   │   (competitor | channel | price) │
                                                │   ├ Gate 2   Reviewer (LLM node)     │
                                                │   ├ Stage 3  Risk (DeepAgent node)   │
                                                │   ├ Gate 3   Reviewer (LLM node)     │
                                                │   ├ Stage 4  Synthesis (LLM node)    │
                                                │   └ Final    Audit (LLM node)        │
                                                │  Conditional edges enforce gates,    │
                                                │  retry caps, and forced-advance.     │
                                                └──────────┬───────────────────────────┘
                                                           │
                            ┌──────────────────────────────┼─────────────────────────────┐
                            ▼                              ▼                             ▼
                   ┌────────────────────┐       ┌─────────────────────┐       ┌──────────────────────┐
                   │ Tools layer        │       │ LangChain chat      │       │ Postgres + pgvector  │
                   │ (LangChain Tools)  │       │ models (per role)   │       │ runs, events,        │
                   │ • web_search       │       │ Anthropic / OpenAI  │       │ messages, artifacts, │
                   │   ├ tavily         │       │ Gemini / Bedrock /  │       │ documents, chunks,   │
                   │   ├ exa            │       │ Ollama              │       │ evidence, settings,  │
                   │   └ perplexity     │       └─────────────────────┘       │ gates, checkpoints   │
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
│   │   │   ├── llm.py                    # LangChain chat model factory (per-role)
│   │   │   ├── tools/
│   │   │   │   ├── web_search.py
│   │   │   │   ├── providers/{tavily,exa,perplexity}.py
│   │   │   │   ├── fetch_url.py
│   │   │   │   ├── rag_search.py
│   │   │   │   ├── read_doc.py
│   │   │   │   ├── artifacts.py
│   │   │   │   └── cite.py               # records evidence, returns src_id
│   │   │   ├── market_entry/
│   │   │   │   ├── graph.py              # LangGraph StateGraph (outer pipeline)
│   │   │   │   ├── state.py              # TypedDict run state shared across nodes
│   │   │   │   ├── nodes/
│   │   │   │   │   ├── framing.py        # LangGraph node (LLM)
│   │   │   │   │   ├── reviewer.py       # LangGraph node (LLM, JSON verdict)
│   │   │   │   │   ├── synthesis.py      # LangGraph node (LLM)
│   │   │   │   │   └── audit.py          # LangGraph node (LLM)
│   │   │   │   ├── deepagents/           # autonomous research nodes
│   │   │   │   │   ├── stage1_foundation.py   # one DeepAgent w/ 3 sub-agents
│   │   │   │   │   ├── stage2_competitive.py  # one DeepAgent w/ 3 sub-agents
│   │   │   │   │   └── stage3_risk.py         # one DeepAgent (risk only)
│   │   │   │   └── prompts/              # all system prompts as files
│   │   │   └── ma/                       # stub for V2
│   │   ├── ingestion/
│   │   │   ├── docling_parser.py
│   │   │   ├── chunker.py
│   │   │   └── embedder.py               # via LangChain Embeddings
│   │   └── workers/
│   │       ├── ingest_worker.py          # asyncio task: parse+chunk+embed
│   │       ├── run_worker.py             # asyncio task: invokes the LangGraph
│   │       └── task_registry.py          # in-process registry of running tasks (cancel hooks)
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
│   │   ├── ReportView.tsx                # MD render with citation links → Sources sidebar
│   │   ├── SourcesSidebar.tsx            # evidence list, jump-to-citation
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

### 6.1 LLM provider layer (LangChain)

`agents/llm.py` exposes `get_chat_model(role: str) -> BaseChatModel` returning a LangChain chat model directly from the provider's official integration package (`langchain-anthropic`, `langchain-openai`, `langchain-google-genai`, `langchain-aws`, `langchain-ollama`). A small `PROVIDER_REGISTRY` dict maps a provider slug to a constructor. No LiteLLM, no extra abstraction layer — LangChain's `BaseChatModel` interface is already the abstraction.

Mapping of `role → {provider, model, params}` lives in `settings.model_overrides` (DB) with env-level defaults. API keys are pulled from the encrypted `provider_keys` table at model construction time and passed explicitly (never via process env, so per-run overrides are safe).

Suggested defaults:

| Role | Default model class |
|---|---|
| framing, reviewer, audit | mid-tier reasoning model (e.g., Claude Sonnet, GPT-4.1-mini) |
| sub-agents (research, inside DeepAgents) | mid-tier with strong tool use |
| synthesis | top-tier reasoning model (e.g., Claude Opus, GPT-4.1) |
| embeddings | provider-native (`text-embedding-3-small` or `voyage-3-lite`) via `langchain-*` Embeddings classes |

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
| `write_todos(...)` | DeepAgents built-in; used by stage DeepAgent nodes for sub-agent planning |

Every tool emits a `tool_call` and `tool_result` event into the run event stream.

### 6.4 Hybrid orchestration (LangGraph + DeepAgents)

The Market Entry pipeline is a **LangGraph `StateGraph`** that owns deterministic control flow. DeepAgents is used **only inside specific stage nodes** that benefit from autonomous tool use across multiple sub-topics. This split keeps gating, retries, persistence, and resumability under LangGraph's deterministic control while letting research stages explore freely.

**Where each framework is used:**

| Concern | Framework | Why |
|---|---|---|
| Outer pipeline (stages, gates, retries, conditional advance, cancel) | **LangGraph** | First-class state machine, conditional edges, checkpointing, replay |
| Framing, Reviewer (gate), Synthesis, Audit | **LangGraph nodes** (single LLM call with structured output) | Need predictable schemas, no autonomous tool loops |
| Stage 1 Foundation, Stage 2 Competitive, Stage 3 Risk research | **DeepAgents wrapped as a LangGraph node** | Each stage has 1–3 sub-topics that benefit from a planner + virtual filesystem + autonomous tool use; DeepAgents handles the inner research loop |
| Tool definitions (web_search, rag_search, fetch_url, etc.) | **LangChain `@tool`** | Both LangGraph nodes and DeepAgents consume LangChain tools natively |

**Shared run state (LangGraph `StateGraph` channels):**

```python
class RunState(TypedDict, total=False):
    run_id: str
    goal: str
    document_ids: list[str]
    framing: FramingBrief                  # populated after Stage 0
    answers: dict                          # questionnaire answers
    artifacts: dict[str, str]              # path -> markdown content (mirrored to DB)
    evidence: list[EvidenceRef]            # accumulating
    stage_attempts: dict[str, int]         # stage_slug -> attempt count
    gate_verdicts: dict[str, GateVerdict]  # stage_slug -> last verdict
    target_agents: list[str] | None        # set by reviewer for retries
    cancelled: bool
```

**Gate logic (conditional edges):** after each research stage node, the graph routes to a Reviewer node. The Reviewer's structured-output verdict drives a conditional edge:

- `verdict.advance` → next stage
- `verdict.reiterate` AND `attempts < settings.max_stage_retries` → back to the same stage node, with `target_agents` set so the DeepAgent reruns only those sub-topics
- `verdict.reiterate` AND `attempts >= settings.max_stage_retries` → forced advance, gaps logged into `audit.md`

`settings.max_stage_retries` is a single global value (default `2`) configurable from the Settings UI; it applies uniformly to every stage.

**Checkpointing:** LangGraph's Postgres checkpointer (`langgraph-checkpoint-postgres`) persists graph state to the same DB. This gives us free crash-resume *between nodes* (we still don't auto-resume mid-tool-call in V1).

**DeepAgent stage nodes:** each stage (Foundation, Competitive, Risk) is a `create_deep_agent(...)` instance whose:

- **Sub-agents** are the per-topic researchers (e.g., Foundation has `market_sizing`, `customer`, `regulatory`).
- **Tools** are the LangChain tools from §6.3.
- **Instructions** include the framing brief, prior-stage artifacts, and (on retry) the reviewer gaps + `target_agents`.
- **Output contract**: writes Markdown sections via `write_artifact` and returns a summary dict the LangGraph node merges into `RunState`.

### 6.5 RAG ingestion pipeline

1. `POST /documents` accepts file upload, stores binary under `/data/uploads/{doc_id}`, inserts a `documents` row with `status='pending'`.
2. An asyncio background task picks it up (registered via `task_registry`): Docling → structured Markdown → token-aware chunker (target ~800 tokens, 100 overlap) → LangChain Embeddings (per active provider) → `chunks(embedding vector(N))`.
3. `documents.status` transitions `pending → parsing → embedding → ready` (or `failed` with error).
4. `rag_search(query, doc_ids?)` performs cosine similarity (`<=>`) with optional filter by document scope.

### 6.6 Run lifecycle

States: `created → questioning → running → cancelling → cancelled | completed | failed`.

1. `POST /runs` with `{task_type, goal, document_ids[]}` → status `created`.
2. Backend schedules a short `framing` asyncio task and returns immediately with status `questioning`. The task invokes the Framing node of the LangGraph and writes the questionnaire artifact (`framing/questionnaire.json`); UI subscribes to SSE and renders the form once the `artifact_update` event for that path arrives.
3. UI submits answers via `POST /runs/{id}/answers` → schedules the `run` asyncio task that drives the rest of the LangGraph from the framing checkpoint → status `running`.
4. Worker executes the staged pipeline, streaming events through Postgres `events` table; the SSE endpoint tails this table.
5. Manual cancel via `POST /runs/{id}/cancel` sets status `cancelling`; the worker checks between stages and after each tool call, finalizes whatever exists, sets `cancelled`.
6. On completion, `final_report.md` artifact exists, status `completed`.

### 6.7 Persistence (Postgres + pgvector)

Core tables (Alembic-managed):

- `users` (single row in V1; column reserved for future multi-user)
- `provider_keys (id, user_id, provider, encrypted_key, created_at)` — Fernet-encrypted
- `settings (user_id, key, value_json)` — active LLM provider/model per role, active search provider, embedding model + dim, etc.
- `tasks (id, slug, name, description, enabled)` — catalog
- `documents (id, user_id, filename, mime, size, status, error, created_at)`
- `chunks (id, document_id, ord, text, embedding vector(N), embedding_model text, metadata jsonb)` — `N` is set at first ingest from the active embedding model's dimension and recorded in `settings.embedding_dim`. Switching embedding model requires a re-ingest migration; this is documented in the Settings UI and not handled automatically in V1.
- `runs (id, user_id, task_id, goal, status, created_at, updated_at, model_snapshot jsonb)`
- `messages (id, run_id, role, content, created_at)` — user-facing chat
- `events (id, run_id, ts, agent, type, payload jsonb)` — full agent trace; SSE source of truth
- `artifacts (id, run_id, path, kind, content, updated_at)` — versionless overwrite-on-write Markdown
- `evidence (id, run_id, src_id, kind, url|chunk_id, title, snippet, accessed_at)` — citation registry
- `gates (id, run_id, stage, attempt, verdict, gaps jsonb, target_agents jsonb, created_at)`
- `langgraph_checkpoints` — managed by `langgraph-checkpoint-postgres`; stores serialized `RunState` per node transition for crash-resume and replay.

Indexes: `chunks` HNSW on `embedding`; `events(run_id, id)` for SSE replay.

### 6.8 SSE streaming

`GET /runs/{id}/stream` returns `text/event-stream`. The handler tails the `events` table by `id > Last-Event-ID`. Event types:

`stage_start`, `stage_complete`, `agent_start`, `agent_complete`, `tool_call`, `tool_result`, `gate_verdict`, `artifact_update`, `usage_update`, `clarification_request` (Stage 0 only), `cancel_ack`, `run_complete`, `error`.

Reconnects resume from `Last-Event-ID`. The events table is the durable log; the SSE handler is a thin tailer.

### 6.9 Soft guardrails

`core/budget.py` accumulates token usage and dollar estimates per run. Token counts come from LangChain's `UsageMetadataCallbackHandler` (attached to every chat-model call); dollar estimates are computed from a small static price table per `(provider, model)` kept in `core/pricing.py`. Every `tool_call` and LLM call emits a `usage_update` event. The UI shows running totals and a Cancel button. No tool ever blocks on budget in V1.

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

The Reviewer is a LangGraph node (single LLM call with structured output via `with_structured_output(GateVerdict)`) invoked after each stage. It reads all artifacts from the just-completed stage and emits a strict JSON verdict (no prose):

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
- Max `settings.max_stage_retries` reiterations per stage (default 2, global, configurable). On the next attempt the conditional edge force-advances and gaps are merged into `RunState` for `audit` to log.
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
4. **Run view (4-pane layout):**
   - **Left:** chat-style transcript (user goal, framing answers, stage narration).
   - **Center-left:** **AgentTrace** — collapsible stage groups, per-agent activity, tool calls with queries and source titles, gate verdicts.
   - **Center-right:** **ReportView** — live Markdown of `final_report.md` (or the latest stage artifacts before synthesis). Inline `[^src_id]` tokens are rendered as clickable chips that scroll/highlight the matching entry in the Sources sidebar.
   - **Right:** **SourcesSidebar** — every evidence entry (title, URL, snippet, accessed-at, provider). Clicking an entry highlights all its inline citations in the report.
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
- **LLM errors** (rate limit, provider outage): LangChain chat models are wrapped with `with_retry(stop_after_attempt=3, exponential_jitter=True)`. If a fallback model is configured for the role (`with_fallbacks`), it is tried next. If still failing, the LangGraph node returns a structured error; the conditional edge routes to a `node_failed` handler that logs an `error` event and either advances with a placeholder gap or, for Synthesis/Audit, marks the run `failed`.
- **Reviewer infinite loops:** prevented by the configurable global cap `settings.max_stage_retries` (default 2).
- **Ingestion failures:** `documents.status='failed'` with error message; surfaced in UI.
- **Worker crash mid-run:** on restart, the worker checks for `runs.status='running'` whose last event is older than N minutes and marks them `failed` (no automatic resume in V1).

---

## 11. Testing Strategy

- **Unit:** chunker, embedder, each search provider adapter (against recorded fixtures), Fernet wrap/unwrap, evidence registration, citation validator.
- **Integration:** ingestion pipeline end-to-end on a small PDF; SSE replay from `Last-Event-ID`.
- **Agent smoke test:** a `FakeChatModel` (LangChain `BaseChatModel` subclass) returns scripted JSON/Markdown keyed by agent role and stage attempt. The `PROVIDER_REGISTRY` exposes provider slug `fake` for tests. The smoke test invokes the LangGraph end-to-end, asserting: stage order, gate `advance`/`reiterate` decisions, retry caps (force-advance after 2), citation enforcement (uncited claim → reviewer reiterate), conditional-edge routing, and final report shape (required sections + non-empty Sources).
- **Frontend:** component tests for `AgentTrace`, `ReportView` citation→sidebar linking, `SourcesSidebar` selection state, `QuestionnaireForm` validation; one Playwright happy-path against the backend smoke run.

---

## 12. Infra & Dev Experience

- `infra/docker-compose.yml`: `postgres` (with pgvector extension), `backend` (uvicorn — also runs background asyncio tasks in-process), `frontend` (next dev). **No Redis, no separate worker container in V1.**

> **V1 single-process trade-off:** because background tasks run inside the FastAPI process, restarting the backend cancels in-flight runs. Resumption uses LangGraph Postgres checkpoints (a manual "resume run" action in V2). For V1 this is acceptable for a local/demo deployment.
- `.env.example` covers `DATABASE_URL`, `REDIS_URL`, `FERNET_KEY`, default LLM provider + model, optional default search provider/key.
- `make dev` brings everything up; seeds tasks catalog.
- Pre-commit: ruff + black + mypy (backend); eslint + prettier (frontend).

---

## 13. Milestones

1. **M1 — Skeleton:** monorepo, docker-compose, FastAPI + Next.js hello, Postgres+pgvector, Alembic baseline.
2. **M2 — Settings + LLM provider layer:** settings UI, encrypted key storage, LangChain provider registry, ping endpoint that calls a chosen model.
3. **M3 — Ingestion:** Docling worker, chunk+embed, `rag_search` tool tested.
4. **M4 — Web search:** Tavily/Exa/Perplexity adapters, provider switch in UI.
5. **M5 — LangGraph harness + SSE:** minimal 2-node `StateGraph` with Postgres checkpointer, run lifecycle persisted, SSE end-to-end in chat UI; one DeepAgent stage node proven inside the graph.
6. **M6 — Market Entry pipeline:** Framing questionnaire (LangGraph node), Stage 1/2/3 DeepAgent nodes, Reviewer gates with conditional edges, Synthesis, Audit, citation enforcement, final report.
7. **M7 — Polish:** AgentTrace UX, Sources sidebar with citation linking, report download, usage panel + cancel, README + screenshots.
8. **M8 — V2 stubs:** M&A task type registered with a placeholder LangGraph + DeepAgent skeleton.

---

## 14. Resolved Decisions (post-review)

1. **Export format:** Markdown only for V1. PDF/PPTX deferred.
2. **Default model roles:** N/A — left to user configuration in Settings; no specific models pinned in the spec. Sensible role labels remain (framing/reviewer/research/synthesis/audit/embeddings).
3. **Worker:** **No Redis in V1.** The run worker uses **plain asyncio background tasks** managed by FastAPI's lifespan + an in-process task registry. arq deferred to V2 when we need horizontal scale.
4. **Gate retry cap:** **Configurable in Settings as a single global value** (default 2) that applies to all stages uniformly. No per-stage configuration in V1.
5. **Citations UX:** **Dedicated Sources sidebar** (not inline hover). The sidebar lists every evidence entry with title, URL, snippet, accessed-at, and a "jump to citations in report" affordance. Inline `[^src_id]` tokens in the report scroll/highlight the corresponding sidebar entry.
6. **Framework split:** Confirmed as designed in §6.4. **DeepAgents** = exploration / R&D / web research (Stage 1/2/3 research nodes — agent has freedom and flexibility). **LangGraph** = audit, review, synthesis, final response, and all deterministic control (gates, retries, advance/retry routing, checkpointing).

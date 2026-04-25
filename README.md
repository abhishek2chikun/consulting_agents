# Consulting Research Agent

Local-first, single-user research agent. Producer-consumer pipeline:
LangGraph orchestrates DeepAgents-style stage agents (framing →
review → research → synthesis → audit) over your own documents
(Docling-parsed) plus pluggable web search (Tavily / Exa /
Perplexity). Output is a Markdown report with `[^src_id]` citations
backed by a per-run `Evidence` table.

## Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2 async, Alembic, Postgres + pgvector.
- **Agents**: LangGraph state machines + `langchain_core` chat models. No LiteLLM.
- **RAG**: Docling for parsing, pgvector for retrieval. No external vector DB.
- **Frontend**: Next.js 16 (App Router) + React 19 + Tailwind v4 + shadcn-style UI.
- **Streaming**: Server-Sent Events with replay (`?last_event_id=` resume).
- **Storage of secrets**: Fernet-encrypted at rest in Postgres.

## Layout

```
backend/    FastAPI app, agents, workers, alembic migrations
frontend/   Next.js 16 app (chat, run workspace, settings)
infra/      docker-compose for Postgres + pgvector
docs/       Plans, ADRs
scripts/    check.sh — run all gates locally
```

## Quick start

### 0. Prereqs
- Python 3.12 + `uv`
- Node 20+ + `pnpm`
- Docker (for Postgres)

### 1. Bring up Postgres
```bash
docker compose -f infra/docker-compose.yml up -d
```

### 2. Configure env
```bash
cp .env.example .env
# generate FERNET_KEY (see comment in .env.example) and paste it in
cp backend/.env.example backend/.env       # if you prefer per-package envs
cp frontend/.env.example frontend/.env.local
```

### 3. Backend
```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

### 4. Frontend
```bash
cd frontend
pnpm install
pnpm dev
```

Open http://localhost:3000.

### 5. Configure providers (in-app)
Visit `/settings`:
- Add at least one LLM provider key (Anthropic / OpenAI / Google / Ollama).
- Pick a search provider (Tavily / Exa / Perplexity) and add its key.
- Optionally override the model used per role
  (`framing` / `review` / `research` / `synthesis` / `audit`).

Keys are encrypted with `FERNET_KEY` before being written to
Postgres.

## Run a research task

1. Pick a task on the home page (V1 ships **Market Entry**; M&A skeleton
   present, full graph pending in M8).
2. Enter a goal.
3. The framing agent produces a clarifying questionnaire — fill it in.
4. The pipeline streams agent messages, gate verdicts, artifact updates,
   and live token/cost usage to the run workspace.
5. The final report renders in the center pane with `[^src_id]` chips.
   Click a chip to scroll its source card into view in the right pane.
6. Cancel anytime via the "Cancel run" button in the Usage panel.

## Run workspace (`/runs/[id]`)

Four panes:
- **Left**: chat stream + agent trace (messages, gate verdicts, artifact writes).
- **Center**: streaming Markdown report with clickable citation chips.
- **Right top**: usage panel — running token totals + USD cost + cancel.
- **Right bottom**: sources sidebar — one card per cited source.

## Quality gates

```bash
bash scripts/check.sh        # backend + frontend in one shot
```
or individually:
```bash
# backend
cd backend && uv run pytest && uv run ruff check . && uv run mypy app

# frontend
cd frontend && pnpm typecheck && pnpm lint && pnpm build
```

## Design docs

- `docs/superpowers/plans/2026-04-25-consulting-research-agent-v1.md` — V1 milestone plan.
- `backend/README.md` — backend module map and conventions.
- `frontend/README.md` — frontend module map.

## Status

V1 milestones M0–M7 complete:
M0 infra → M1 settings/providers → M2 SSE plumbing → M3 chat shell
→ M4 ingestion + RAG → M5 run lifecycle + framing schema → M6
market-entry agent pipeline → **M7 polish (token/cost tracking,
citation chips, evidence sidebar, 4-pane workspace)**.

M8 (M&A consultant) tracked separately.

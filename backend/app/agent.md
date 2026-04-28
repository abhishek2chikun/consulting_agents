# app — agent.md

## Status
**Active (V1.6).**
Application factory now mounts health/settings/ping/tasks/documents/runs
routers, runs a lifespan startup sweep for stale running runs, and hosts
the shared consulting runtime used by `market_entry`, `pricing`, and
`profitability`.

---

## Purpose

Top-level package for the FastAPI backend. Hosts the application factory
(`create_app`) which wires the routers exposed by submodules, runs
startup recovery for stale `running` rows, and exposes the run lifecycle
API (`/runs`, SSE stream, artifact/evidence access) that fronts the
shared consulting runtime.

---

## Directory Structure
```text
app/
  __init__.py
  main.py        # create_app() and module-level `app` instance
  core/          # cross-cutting config / utilities (see app/core/agent.md)
    config.py
    db.py
    crypto.py
  models/        # ORM models + registry (see app/models/agent.md)
    user.py
    settings_kv.py
    provider_key.py
  services/      # domain services (see app/services/agent.md)
    settings_service.py
  schemas/       # Pydantic DTOs for the HTTP API (see app/schemas/agent.md)
    settings.py
  api/           # FastAPI routers (see app/api/agent.md)
    settings.py
    health.py
    ping.py
    tasks.py
    documents.py
    runs.py
  agents/        # LLM registry + shared consulting runtime (see app/agents/agent.md)
    llm.py
    _engine/      # shared consulting runtime (skills, workers, recovery)
    budget.py     # per-run token/cost accounting callbacks
    ma/           # M&A stub runtime
    market_entry/
    pricing/
    profitability/
    tools/
      __init__.py
      cite.py
      fetch_url.py
      rag_search.py
      read_doc.py
      web_search.py
      write_artifact.py
      providers/
        base.py
        duckduckgo.py
        tavily.py
        exa.py
        perplexity.py
  ingestion/     # PDF parsing + chunking + embedding pipeline (see app/ingestion/agent.md)
    __init__.py
    docling_parser.py
    chunker.py
    embedder.py
    worker.py
  workers/       # background run execution / heartbeat / timeout loop
    run_worker.py
```

### Corresponding Tests
```text
backend/tests/test_health.py
backend/tests/integration/test_settings_api.py    # exercises the mounted /settings router
backend/tests/integration/test_health_search.py    # exercises /health/search diagnostics
backend/tests/integration/test_run_lifecycle.py
backend/tests/integration/test_run_recovery.py
backend/tests/integration/test_run_timeout.py
```

---

## Public API
```python
from app.main import create_app, app  # FastAPI factory + module-level instance
```

`create_app()` mounts:
- `GET /health`
- `GET /health/search`
- `app.api.settings.router` (prefix `/settings`)
- `app.api.ping.router` (prefix `/ping`)
- `app.api.tasks.router` (prefix `/tasks`)
- `app.api.documents.router` (prefix `/documents`)
- `app.api.runs.router` (prefix `/runs`)

It also runs `sweep_stale_runs()` during lifespan startup so stale
`running` rows are marked failed before the app begins serving traffic.

---

## Dependencies
| Imports from | What |
|---|---|
| `fastapi` | `FastAPI` app class |
| `app.core.config` | `get_settings()` |
| `app.api.health` | `router` (mounted at `/health/search`) |
| `app.api.settings` | `router` (mounted at `/settings`) |
| `app.api.ping` | `router` (mounted at `/ping`) |
| `app.api.tasks` | `router` (mounted at `/tasks`) |
| `app.api.documents` | `router` (mounted at `/documents`) |
| `app.api.runs` | `router` (mounted at `/runs`) |
| `app.agents._engine.recovery` | stale-run startup sweep |

| Consumed by | What |
|---|---|
| `tests.test_health` | exercises `/health` via `create_app()` |
| `tests.integration.test_settings_api` | exercises `/settings/*` via `create_app()` |
| `tests.integration.test_health_search` | exercises `/health/search` via `create_app()` |
| `tests.integration.test_run_recovery` | verifies startup recovery wiring |
| `uvicorn` | serves `app.main:app` |

---

## Config

Reads settings via `app.core.config.get_settings()`. No module-local config.

---

## Current Progress

- `create_app()` factory implemented and mounting all current routers,
  including `/runs`.
- `/health` returns `{"status": "ok", "env": settings.app_env}`.
- `/health/search` probes configured search provider and returns top-3 titles.
- Lifespan startup now runs stale-run recovery based on heartbeat /
  started-at / created-at liveness.
- Ingestion stack (M3.4-M3.6), agent tooling, and the shared consulting
  runtime are now present.

## Next Steps
1. Extend startup/lifespan work only when new recovery or warmup duties
   have a clear runtime benefit.
2. Keep `/runs` and SSE DTOs aligned with the frontend live-run views as
   worker child-node rendering evolves.
3. Revisit the import-time `app = create_app()` pattern only if startup
   side effects become a measurable problem in deployment.

## Known Issues / Blockers
- None currently.

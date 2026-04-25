# app — agent.md

## Status
**Active (M4.7 in progress).**
Application factory now mounts health/settings/ping/tasks/documents
routers plus search-health diagnostics (`GET /health/search`).
Submodules include ingestion (`docling -> chunk -> embed`) and
agent tools (`rag_search` + search-provider adapters).

---

## Purpose

Top-level package for the FastAPI backend. Hosts the application factory
(`create_app`) which wires the routers exposed by submodules. Eventually
adds middleware, lifespan events, and dependency providers for
downstream submodules (websockets, agent runtime, retrieval).

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
  agents/        # LLM provider registry + chat model factory (see app/agents/agent.md)
    llm.py
    tools/
      __init__.py
      rag_search.py
      providers/
        base.py
        tavily.py
        exa.py
        perplexity.py
  ingestion/     # PDF parsing + chunking + embedding pipeline (see app/ingestion/agent.md)
    __init__.py
    docling_parser.py
    chunker.py
    embedder.py
    worker.py
```

### Corresponding Tests
```text
backend/tests/test_health.py
backend/tests/integration/test_settings_api.py    # exercises the mounted /settings router
backend/tests/integration/test_health_search.py    # exercises /health/search diagnostics
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

| Consumed by | What |
|---|---|
| `tests.test_health` | exercises `/health` via `create_app()` |
| `tests.integration.test_settings_api` | exercises `/settings/*` via `create_app()` |
| `tests.integration.test_health_search` | exercises `/health/search` via `create_app()` |
| `uvicorn` | serves `app.main:app` |

---

## Config

Reads settings via `app.core.config.get_settings()`. No module-local config.

---

## Current Progress

- `create_app()` factory implemented and mounting all current routers.
- `/health` returns `{"status": "ok", "env": settings.app_env}`.
- `/health/search` probes configured search provider and returns top-3 titles.
- Ingestion stack (M3.4-M3.6) and RAG tooling (M3.7) are now present.
- Search-provider adapters (M4.1-M4.4) and frontend test-search wiring (M4.7) landed.

## Next Steps
1. Add run lifecycle routers under `api/` (`runs.py`, SSE stream endpoints).
2. Add lifespan handler in `create_app()` for startup/shutdown (DB
   pool, agent runtime warmup).
3. When the lifespan handler lands, move the module-level
   `app = create_app()` to a dedicated `app/asgi.py` to avoid
   import-time side effects (DB pool init on every `import app.main`).

## Known Issues / Blockers
- None currently.

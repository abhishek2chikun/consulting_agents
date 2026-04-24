# app — agent.md

## Status
**Active scaffolding (M2.5).**
FastAPI application factory is in place with `/health` plus the M2.4
Settings router mounted at `/settings`. M2.5 added `agents/` (LLM
provider registry + `get_chat_model`). Submodules: `core/` (config,
db, crypto), `models/` (ORM), `services/` (domain logic),
`schemas/` (Pydantic DTOs), `api/` (HTTP routers), `agents/` (LLM
client factory; future LangGraph nodes).

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
  agents/        # LLM provider registry + chat model factory (see app/agents/agent.md)
    llm.py
```

### Corresponding Tests
```text
backend/tests/test_health.py
backend/tests/integration/test_settings_api.py    # exercises the mounted /settings router
```

---

## Public API
```python
from app.main import create_app, app  # FastAPI factory + module-level instance
```

`create_app()` mounts:
- `GET /health`
- `app.api.settings.router` (prefix `/settings`)

---

## Dependencies
| Imports from | What |
|---|---|
| `fastapi` | `FastAPI` app class |
| `app.core.config` | `get_settings()` |
| `app.api.settings` | `router` (mounted at `/settings`) |

| Consumed by | What |
|---|---|
| `tests.test_health` | exercises `/health` via `create_app()` |
| `tests.integration.test_settings_api` | exercises `/settings/*` via `create_app()` |
| `uvicorn` | serves `app.main:app` |

---

## Config

Reads settings via `app.core.config.get_settings()`. No module-local config.

---

## Current Progress

- `create_app()` factory implemented.
- `/health` returns `{"status": "ok", "env": settings.app_env}`.
- Settings router mounted at `/settings` (M2.4).
- Module-level `app = create_app()` exposed for ASGI servers.

## Next Steps
1. Add additional routers under `api/` per milestone (`runs.py`,
   `documents.py`, `websocket.py`).
2. Add lifespan handler in `create_app()` for startup/shutdown (DB
   pool, agent runtime warmup).
3. When the lifespan handler lands, move the module-level
   `app = create_app()` to a dedicated `app/asgi.py` to avoid
   import-time side effects (DB pool init on every `import app.main`).

## Known Issues / Blockers
- None currently.

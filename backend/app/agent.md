# app — agent.md

## Status
**Boilerplate**
FastAPI application factory and a single `/health` endpoint exist. No routers,
middleware, database wiring, auth, or agent runtime yet. Submodules are empty
beyond `core/`.

---

## Purpose

Top-level package for the FastAPI backend. Hosts the application factory
(`create_app`) and will eventually wire routers, middleware, lifespan events,
and dependency providers for downstream submodules (api, db, agents, services).

---

## Directory Structure
```text
app/
  __init__.py
  main.py        # create_app() and module-level `app` instance
  core/          # cross-cutting config / utilities (see app/core/agent.md)
    __init__.py
    config.py
    agent.md
```
### Corresponding Tests
```text
backend/tests/test_health.py
```

---

## Public API
```python
from app.main import create_app, app  # FastAPI factory + module-level instance
```

---

## Dependencies
| Imports from | What |
|---|---|
| `fastapi` | `FastAPI` app class |
| `app.core.config` | `get_settings()` |

| Consumed by | What |
|---|---|
| `tests.test_health` | exercises `/health` via `create_app()` |
| `uvicorn` (future) | will serve `app.main:app` |

---

## Config

Reads settings via `app.core.config.get_settings()`. No module-local config.

---

## Current Progress

- `create_app()` factory implemented.
- `/health` returns `{"status": "ok", "env": settings.app_env}`.
- Module-level `app = create_app()` exposed for ASGI servers.

## Next Steps
1. Add `api/` subpackage with versioned routers (e.g. `api/v1/`).
2. Add `db/` subpackage for async SQLAlchemy engine/session and Alembic wiring.
3. Add lifespan handler in `create_app()` for startup/shutdown (DB pool, etc.).
4. When the lifespan handler lands (likely M1.4), move the module-level
   `app = create_app()` to a dedicated `app/asgi.py` to avoid import-time
   side effects (DB pool init on every `import app.main`).

## Known Issues / Blockers
- None currently.

# app.core — agent.md

## Status
**Scaffolding**
`Settings` (pydantic-settings) + cached accessor, plus the async SQLAlchemy
engine, session factory, and declarative `Base`. No security helpers,
encryption utilities, or logging config yet.

---

## Purpose

Cross-cutting infrastructure for the backend: typed configuration, and (in
later milestones) Fernet encryption helpers, password hashing, and structured
logging setup. Things that have no natural home in a feature package.

---

## Directory Structure
```text
app/core/
  __init__.py
  config.py    # Settings + get_settings()
  db.py        # engine, AsyncSessionLocal, get_session, Base
```
### Corresponding Tests
```text
backend/tests/integration/test_db.py   # exercises AsyncSessionLocal against real Postgres
```

---

## Public API
```python
from app.core.config import Settings, get_settings

settings: Settings = get_settings()
settings.app_env       # str
settings.database_url  # str
settings.fernet_key    # str

from app.core.db import Base, engine, AsyncSessionLocal, get_session

# `Base` — SQLAlchemy 2.x DeclarativeBase; ORM models inherit from it.
# `engine` — module-level async engine bound to settings.database_url.
# `AsyncSessionLocal` — `async_sessionmaker(...)` factory.
# `get_session` — FastAPI dependency yielding an AsyncSession,
#                 with rollback-on-exception and guaranteed close.
```

---

## Dependencies
| Imports from | What |
|---|---|
| `pydantic_settings` | `BaseSettings`, `SettingsConfigDict` |
| `functools` | `lru_cache` |
| `sqlalchemy.ext.asyncio` | `create_async_engine`, `async_sessionmaker`, `AsyncSession` |
| `sqlalchemy.orm` | `DeclarativeBase` |

| Consumed by | What |
|---|---|
| `app.main` | reads `settings.app_env` for `/health` |
| `alembic/env.py` | imports `Base` for `target_metadata`, reads `settings.database_url` |
| `tests.integration.test_db` | uses `AsyncSessionLocal` to run `SELECT 1` |

---

## Config

Loads from process environment and from `backend/.env` (if present).
Recognized variables (see `backend/.env.example`):

- `APP_ENV` — `development` / `staging` / `production`
- `DATABASE_URL` — async SQLAlchemy URL (`postgresql+asyncpg://...`)
- `FERNET_KEY` — base64 Fernet key for at-rest secret encryption

Unknown env vars are ignored (`extra="ignore"`).

---

## Current Progress

- `Settings` model with three fields and sensible local defaults.
- `get_settings()` returns a process-wide cached instance.
- `db.py` exposes async `engine`, `AsyncSessionLocal`, the `get_session`
  FastAPI dependency, and the `Base` declarative class. Verified end-to-end
  against the dockerised Postgres via `tests/integration/test_db.py` and
  Alembic baseline migration `0001`.

## Next Steps
1. Add Fernet encryption helpers (`encrypt`/`decrypt`) using `settings.fernet_key`.
2. Add password hashing helpers (passlib/bcrypt).
3. Add structured logging configuration.
4. Add tests for `Settings` env loading and the encryption helpers once they land.

## Known Issues / Blockers
- `fernet_key` defaults to `""`, which will fail at first real use. Acceptable
  for scaffold; must be enforced (validator) once any consumer reads it.
- `get_settings()` is `lru_cache`d — tests that mutate env vars must call
  `get_settings.cache_clear()` (or use FastAPI `app.dependency_overrides`) to
  see the new values.
- `db.py` resolves `settings.database_url` at import time. The default in
  `Settings` is aligned with the dockerised dev stack
  (`postgresql+asyncpg://consulting:consulting@localhost:5432/consulting`);
  staging / production must override via `DATABASE_URL`. We have not yet
  added a startup probe that validates the connection.

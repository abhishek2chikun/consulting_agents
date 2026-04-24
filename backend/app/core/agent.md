# app.core — agent.md

## Status
**Scaffolding**
`Settings` (pydantic-settings) + cached accessor, async SQLAlchemy engine /
session factory / declarative `Base`, and Fernet `wrap` / `unwrap` helpers
for at-rest secret encryption. No password hashing or logging config yet.

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
  crypto.py    # wrap / unwrap / generate_key (Fernet)
```
### Corresponding Tests
```text
backend/tests/integration/test_db.py   # exercises AsyncSessionLocal against real Postgres
backend/tests/unit/test_crypto.py      # Fernet wrap/unwrap roundtrip + error paths
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

from app.core.crypto import wrap, unwrap, generate_key

# `wrap(plaintext: str) -> str` — Fernet-encrypt; raises ValueError if
#     `settings.fernet_key` is empty.
# `unwrap(ciphertext: str) -> str` — Fernet-decrypt; raises ValueError if
#     unconfigured, `cryptography.fernet.InvalidToken` on bad/forged token.
# `generate_key() -> str` — convenience helper for dev/scripts; returns a
#     fresh base64 Fernet key suitable for `FERNET_KEY`.
```

---

## Dependencies
| Imports from | What |
|---|---|
| `pydantic_settings` | `BaseSettings`, `SettingsConfigDict` |
| `functools` | `lru_cache` |
| `sqlalchemy.ext.asyncio` | `create_async_engine`, `async_sessionmaker`, `AsyncSession` |
| `sqlalchemy.orm` | `DeclarativeBase` |
| `cryptography.fernet` | `Fernet` (and `InvalidToken`, propagated to callers) |

| Consumed by | What |
|---|---|
| `app.main` | reads `settings.app_env` for `/health` |
| `alembic/env.py` | imports `Base` for `target_metadata`, reads `settings.database_url` |
| `tests.integration.test_db` | uses `AsyncSessionLocal` to run `SELECT 1` |
| `tests.unit.test_crypto` | exercises `wrap` / `unwrap` / `generate_key` |

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
- `crypto.py` exposes `wrap` / `unwrap` / `generate_key` over
  `cryptography.fernet.Fernet`, reading `settings.fernet_key` fresh on each
  call (no cached cipher) and raising `ValueError("FERNET_KEY not configured")`
  when the key is empty. `InvalidToken` is allowed to propagate to callers.
  Covered by `tests/unit/test_crypto.py` (roundtrip, wrong-key, IV
  uniqueness, empty-token, unconfigured-key, key-generation).

## Next Steps
1. Add password hashing helpers (passlib/bcrypt).
2. Add structured logging configuration.
3. Add tests for `Settings` env loading.

## Known Issues / Blockers
- `fernet_key` defaults to `""` in `Settings`. `crypto.wrap`/`unwrap` raise
  `ValueError("FERNET_KEY not configured")` at call time when this happens,
  so misconfiguration fails loudly rather than silently. Production / staging
  must export a real key (use `crypto.generate_key()` to mint one).
- `get_settings()` is `lru_cache`d — tests that mutate env vars must call
  `get_settings.cache_clear()` (or use FastAPI `app.dependency_overrides`) to
  see the new values.
- `db.py` resolves `settings.database_url` at import time. The default in
  `Settings` is aligned with the dockerised dev stack
  (`postgresql+asyncpg://consulting:consulting@localhost:5432/consulting`);
  staging / production must override via `DATABASE_URL`. We have not yet
  added a startup probe that validates the connection.
- **Module-level `engine` / `AsyncSessionLocal` are loop-bound.** asyncpg's
  connection pool is created lazily on first use and binds to whichever
  event loop is running at that moment. Subsequent use from a *different*
  loop raises `InterfaceError: another operation is in progress` and/or
  `RuntimeError: Event loop is closed` when the pool is GC'd. Today this
  works in two contexts:
  - **Production:** Uvicorn runs a single event loop for the process
    lifetime, so the pool stays valid.
  - **Tests:** `backend/pyproject.toml` pins pytest-asyncio to
    `asyncio_default_test_loop_scope = "session"` and
    `asyncio_default_fixture_loop_scope = "session"`, so all async tests
    share one loop.

  **Must revisit before M3** (streaming + task_registry + any background
  worker that may spawn its own loop). Likely fix: replace the
  module-level globals with a `get_engine()` / `get_sessionmaker()`
  factory keyed by `asyncio.get_running_loop()`, or assert at startup
  that we're on the expected loop and document the constraint loudly.
  Until then, do not import and use `engine` / `AsyncSessionLocal` from a
  loop other than the one that owns the running app/test session.

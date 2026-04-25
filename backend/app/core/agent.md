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
  config.py         # Settings + get_settings()
  db.py             # engine, AsyncSessionLocal, get_session, Base
  crypto.py         # wrap / unwrap / generate_key (Fernet)
  task_registry.py  # TaskRegistry + TASK_REGISTRY (in-process asyncio.Task tracker)
```
### Corresponding Tests
```text
backend/tests/integration/test_db.py   # exercises AsyncSessionLocal against real Postgres
backend/tests/unit/test_crypto.py      # Fernet wrap/unwrap roundtrip + error paths
backend/tests/unit/test_task_registry.py  # register / get / cancel / auto-cleanup
```

---

## Public API
```python
from app.core.config import Settings, get_settings

settings: Settings = get_settings()
settings.app_env       # str
settings.database_url  # str
settings.fernet_key    # str
settings.embedding_dim # int (default 1536, env: EMBEDDING_DIM)
settings.upload_dir    # pathlib.Path (default Path("data/uploads"), env: UPLOAD_DIR)

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

from app.core.task_registry import TASK_REGISTRY, TaskRegistry

# `TaskRegistry` — in-process dict mapping `str` keys → `asyncio.Task`.
#     `register(key, task)` overwrites silently and arms a done-callback
#     that auto-prunes the entry once the task completes (only if the
#     entry still points to that specific task — overwrites are safe).
# `TASK_REGISTRY` — module-level singleton used by the documents API to
#     track in-flight `run_ingest(...)` background tasks (key
#     `f"ingest:{doc_id}"`). V1 alternative to a Celery/Redis worker:
#     the FastAPI process owns its background work, and a backend
#     restart cancels every in-flight task. Future cancel/run-abort
#     endpoints look the task up by key and call `.cancel()`.
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
| `app.api.documents` | uses `TASK_REGISTRY` to track ingest background tasks |
| `app.ingestion.worker` | uses `AsyncSessionLocal` to own its DB sessions |
| `alembic/env.py` | imports `Base` for `target_metadata`, reads `settings.database_url` |
| `tests.integration.test_db` | uses `AsyncSessionLocal` to run `SELECT 1` |
| `tests.unit.test_crypto` | exercises `wrap` / `unwrap` / `generate_key` |
| `tests.unit.test_task_registry` | exercises register / get / cancel / cleanup |

---

## Config

Loads from process environment and from `backend/.env` (if present).
Recognized variables (see `backend/.env.example`):

- `APP_ENV` — `development` / `staging` / `production`
- `DATABASE_URL` — async SQLAlchemy URL (`postgresql+asyncpg://...`)
- `FERNET_KEY` — base64 Fernet key for at-rest secret encryption
- `EMBEDDING_DIM` — pgvector embedding dimension (int, default 1536). Read
  by `app.models.chunk.Chunk` at import time to size the `vector(N)`
  column. Changing it requires a backend restart AND a fresh migration
  (the migration also reads `EMBEDDING_DIM` directly via `os.environ`).
- `UPLOAD_DIR` — filesystem destination for uploaded document binaries
  (`pathlib.Path`, default `Path("data/uploads")`). Resolved relative
  to the process working directory (i.e. the repo root when uvicorn
  is launched via the project Makefile). `DocumentService` ensures
  the directory exists before writing.

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

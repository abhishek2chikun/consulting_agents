# alembic — agent.md

## Status
**Active (revisions 0001, 0002, 0003)**
Async-template Alembic. Three revisions:
`0001_baseline` (empty chain anchor), `0002_users_and_settings`
(creates `users` + `settings_kv`, seeds the V1 singleton user), and
`0003_provider_keys` (creates `provider_keys` with unique
`(user_id, provider)` constraint and `user_id` index). All ORM models
live under `app.models`; `env.py` imports `app.models` explicitly to
register all ORM classes on `Base.metadata` for autogenerate. Importing
`Base` alone is NOT sufficient — the model modules must be imported for
their `mapped_column` declarations to run.

---

## Purpose

Database schema migrations for the backend. Generated via SQLAlchemy 2.x
ORM models (autogenerate) once they exist; until then the baseline holds
the chain so future revisions stack cleanly.

The runtime app uses async SQLAlchemy (`app.core.db`); migrations also
run through the async engine (the generated `-t async` template),
sharing the same `DATABASE_URL` for a single source of truth.

---

## Directory Structure
```text
backend/
  alembic.ini                  # alembic config; sqlalchemy.url is set in env.py
  alembic/
    env.py                     # async migration runner; loads Base + DATABASE_URL
    script.py.mako             # revision file template (default)
    README                     # alembic scaffolding readme
    agent.md                   # this file
    versions/
      0001_baseline.py            # empty baseline revision
      0002_users_and_settings.py  # users + settings_kv + singleton seed
      0003_provider_keys.py       # provider_keys (encrypted API keys)
```
### Corresponding Tests
```text
None directly. `backend/tests/integration/test_db.py` exercises the
underlying engine (`SELECT 1`); migrations are smoke-tested by
`make migrate` / `alembic upgrade head` against the docker DB.
```

---

## Public API

The user-facing surface is the Alembic CLI, invoked through `uv`:

```bash
# from backend/
uv run alembic upgrade head                          # apply pending migrations
uv run alembic revision --autogenerate -m "message"  # create a new revision
uv run alembic downgrade -1                          # roll back one revision
uv run alembic history --verbose
```

Or via root `Makefile` shortcuts:

```bash
make migrate                          # alembic upgrade head
make migrate-rev m="add users table"  # alembic revision --autogenerate -m "..."
```

Revision files in `versions/` define `upgrade()` / `downgrade()` per the
standard Alembic contract.

---

## Dependencies
| Imports from | What |
|---|---|
| `alembic` | `context`, `op`, revision machinery |
| `sqlalchemy` (+ `sqlalchemy.ext.asyncio`) | async engine factory used by `env.py` |
| `app.core.config` | `get_settings()` to read `DATABASE_URL` |
| `app.core.db` | `Base` for `target_metadata` (autogenerate) |

| Consumed by | What |
|---|---|
| Local dev workflow | `make migrate` before running the backend |
| CI (future) | apply migrations against ephemeral Postgres |

---

## Config

- `alembic.ini` — `script_location = alembic` (relative to `backend/`).
  `sqlalchemy.url` is intentionally **not** set here; `env.py` injects it
  from `app.core.config.Settings` so it picks up `DATABASE_URL` /  `.env`.
- `env.py` is the async-template variant (`alembic init -t async`). It
  builds an `async_engine_from_config(...)` with `pool.NullPool` and runs
  `do_run_migrations` via `connection.run_sync(...)`.
- `target_metadata = Base.metadata`. Once ORM models exist they must be
  imported (transitively) before the metadata is read so autogenerate
  sees them.

---

## Current Progress

- Async-template `env.py` wired to `Settings.database_url` and
  `app.core.db.Base.metadata`.
- `0001_baseline.py` — empty chain anchor, applied.
- `0002_users_and_settings.py` — creates `users` (singleton-seeded via
  raw SQL `INSERT … ON CONFLICT (id) DO NOTHING`) and `settings_kv`
  (composite PK `(user_id, key)`, FK `users.id` ON DELETE CASCADE,
  `value` JSONB NOT NULL). Verified clean upgrade → downgrade → upgrade
  round-trip against the docker DB.
- `0003_provider_keys.py` — creates `provider_keys` (UUID PK, FK
  `users.id` ON DELETE CASCADE on `user_id` (indexed), `provider`
  String(64), `encrypted_key` Text, server-defaulted `created_at` /
  `updated_at`, unique constraint `uq_provider_keys_user_provider` on
  `(user_id, provider)`). `alembic check` reports no drift; downgrade →
  upgrade round-trip clean.

## Next Steps
1. M2.2 — `runs`, `stages`, `artifacts` tables (autogenerate from new
   models in `app.models`; review the diff carefully before committing).
2. Add a `pgvector` extension migration (`CREATE EXTENSION IF NOT EXISTS
   vector`) once the embedding table lands.
3. Wire migrations into CI against an ephemeral Postgres service.
4. Once any model is added without re-importing in `app/models/__init__.py`,
   autogenerate will silently miss it — keep the registry in sync.

## Known Issues / Blockers
- Async `env.py` requires `asyncpg` available even for offline mode work
  (because the engine is built up-front). If we ever need pure-offline
  `--sql` generation without asyncpg installed, swap to the sync template
  and add `psycopg[binary]` as a dependency at that time.
- No automatic check that `target_metadata` is empty vs the live DB; the
  baseline relies on humans not forgetting to import models before
  autogenerating.

# app.models — agent.md

## Status
**Active (M3.2).** Six ORM models landed: `User` (V1 single-row table),
`SettingKV` (per-user JSONB key/value store), `ProviderKey`
(per-user Fernet-encrypted LLM provider API keys), `TaskType`
(catalog of consulting workflows), `Document` (uploaded source file with
ingestion lifecycle), and `Chunk` (text span + pgvector embedding with
HNSW cosine index). Migrations `0002`, `0003`, `0004`, `0005` create the
underlying tables; `0002` seeds the singleton user and `0004` seeds the
V1 task catalog (`market_entry` enabled, `ma` disabled).

---

## Purpose

Holds SQLAlchemy 2.x ORM model definitions. One ORM class per file. The
package `__init__.py` re-exports every class so that:

1. Application code can write `from app.models import User, SettingKV`
   without caring about file layout.
2. Importing `app.models` (which `alembic/env.py` does transitively via
   `from app.core.db import Base`) registers every model on
   `Base.metadata`, which is what Alembic `--autogenerate` diffs against.

When adding a new model: create `app/models/<name>.py` with the class,
then add it to `app/models/__init__.py`'s import list and `__all__`.

---

## Directory Structure
```text
app/models/
  __init__.py        # registry + re-exports
  user.py            # User + SINGLETON_USER_ID constant
  settings_kv.py     # SettingKV (composite-PK JSONB store)
  provider_key.py    # ProviderKey (encrypted per-user provider API keys)
  task_type.py       # TaskType (consulting workflow catalog row)
  document.py        # Document + DocumentStatus enum (upload lifecycle)
  chunk.py           # Chunk (text span + pgvector embedding + HNSW index)
```

### Corresponding Tests
```text
backend/tests/integration/test_settings_kv.py
  test_upsert_and_read_setting   # exercises ON CONFLICT upsert + read-back
backend/tests/integration/test_settings_service.py
  test_set_provider_key_stores_encrypted     # raw column holds Fernet ciphertext, not plaintext
  test_get_provider_key_returns_plaintext    # round-trip + None for missing
  test_overwrite_provider_key_replaces_value # upsert keeps row count == 1
backend/tests/integration/test_documents_orm.py
  test_insert_document_and_chunk_roundtrip   # Document + Chunk insert/read with pgvector embedding
```

`User` has no dedicated test yet — it is exercised transitively via
`SettingKV.user_id` and `ProviderKey.user_id` FKs and the singleton seed
in migration `0002`.

---

## Public API

```python
from app.models import (
    SINGLETON_USER_ID,
    Chunk,
    Document,
    DocumentStatus,
    ProviderKey,
    SettingKV,
    TaskType,
    User,
)

# User: V1 single-user; one seeded row with id == SINGLETON_USER_ID.
#   Columns: id (UUID PK, default uuid4), created_at (timestamptz, server_default NOW()).
# SINGLETON_USER_ID: uuid.UUID = '00000000-0000-0000-0000-000000000001'.
#   Use this UUID anywhere a user_id is needed in V1.
# SettingKV: per-user JSONB key/value table.
#   Columns: user_id (UUID FK -> users.id ON DELETE CASCADE, PK),
#            key (str, PK), value (JSONB, NOT NULL),
#            updated_at (timestamptz, server_default NOW(), onupdate NOW()).
#   Composite PK on (user_id, key) — use `ON CONFLICT (user_id, key)` for upserts.
# ProviderKey: per-user, per-provider Fernet-encrypted API key.
#   Columns: id (UUID PK, default uuid4), user_id (UUID FK -> users.id ON DELETE CASCADE, indexed),
#            provider (String(64)), encrypted_key (Text — base64 Fernet token),
#            created_at, updated_at (timestamptz, server defaults).
#   Unique constraint `uq_provider_keys_user_provider` on (user_id, provider) —
#   use `ON CONFLICT (user_id, provider)` for upserts. Plaintext NEVER lands in
#   `encrypted_key`; encryption is owned by `app.services.settings_service`.
# TaskType: catalog of consulting workflows the agent runtime can execute.
#   Columns: slug (String(64) PK — public stable identifier),
#            name (String(128)), description (Text, nullable),
#            enabled (Boolean, default false, server_default false).
#   Seeded by migration 0004 with rows: 'market_entry' (enabled), 'ma' (disabled).
#   Read-only over HTTP via `GET /tasks`; new types are added by inserting
#   rows (typically via migration), not by shipping new code.
# Document: an uploaded source file, owned by a user, tracked through ingestion.
#   Columns: id (UUID PK), user_id (UUID FK -> users.id ON DELETE CASCADE, indexed),
#            filename (String(512)), mime (String(128)), size (Integer),
#            status (DocumentStatus enum, server_default 'pending'),
#            error (Text, nullable), created_at, updated_at (timestamptz).
# DocumentStatus: enum.StrEnum with values pending|parsing|embedding|ready|failed.
#   Backed by a native Postgres `document_status` enum type.
# Chunk: a text span + embedding belonging to a Document.
#   Columns: id (UUID PK), document_id (UUID FK -> documents.id ON DELETE CASCADE, indexed),
#            ord (Integer — position within the doc), text (Text),
#            embedding (vector(N) — N from settings.embedding_dim, default 1536),
#            embedding_model (String(128)),
#            metadata (JSONB, server_default '{}').
#   IMPORTANT: the Python attr is `metadata_` (with trailing underscore) because
#   `metadata` collides with `DeclarativeBase.metadata`. The DB column is named
#   `metadata` per the spec.
#   HNSW index `ix_chunks_embedding_hnsw` on `embedding` with `vector_cosine_ops`.
```

---

## Dependencies

| Imports from | What |
|---|---|
| `sqlalchemy` | `DateTime`, `Enum`, `ForeignKey`, `Index`, `Integer`, `String`, `Text`, `UniqueConstraint`, `func`, `text` |
| `sqlalchemy.dialects.postgresql` | `UUID(as_uuid=True)`, `JSONB` |
| `sqlalchemy.orm` | `Mapped`, `mapped_column` |
| `pgvector.sqlalchemy` | `Vector(N)` (vector column type) |
| `app.core.db` | `Base` (DeclarativeBase) |
| `app.core.config` | `get_settings()` (for `embedding_dim` at import time, in `chunk.py`) |

| Consumed by | What |
|---|---|
| `alembic/env.py` | indirectly — relies on `Base.metadata` being populated |
| `alembic/versions/0002_users_and_settings.py` | creates `users` + `settings_kv` |
| `alembic/versions/0003_provider_keys.py` | creates `provider_keys` |
| `alembic/versions/0004_task_catalog.py` | creates `task_types` + seeds catalog |
| `alembic/versions/0005_documents_and_chunks.py` | creates `documents` + `chunks` (HNSW index) |
| `app.api.tasks` | reads `TaskType` rows for `GET /tasks` |
| `app.services.settings_service` | reads/writes `ProviderKey` rows |
| `tests/integration/test_settings_kv.py` | upsert/read-back coverage |
| `tests/integration/test_settings_service.py` | encrypted-at-rest + upsert coverage |
| Future settings service expansion (M2.4) | typed reads/writes against `SettingKV` |

---

## Config

None at this layer. The connection pool, async engine, and session
factory live in `app.core.db`. Per-key validation of `SettingKV.value`
is intentionally deferred to the service layer — the column accepts any
JSON-serializable shape today.

---

## Current Progress

- M2.1 — `User`, `SettingKV`, migration `0002`, singleton seed, integration
  test. Verified end-to-end against the dockerised Postgres (upgrade →
  downgrade → upgrade round-trip is clean; ON CONFLICT DO NOTHING keeps
  the seed idempotent).
- M2.3 — `ProviderKey` (Fernet-encrypted provider API keys), migration
  `0003`, unique constraint on `(user_id, provider)`, index on `user_id`.
  `alembic check` reports no drift; downgrade → upgrade round-trip
  verified.
- M3.1 — `TaskType` lookup table seeded by migration `0004`. Slug PK
  doubles as public identifier; `enabled` flag (with both ORM `default`
  and `server_default text("false")` for autogenerate parity) gates which
  task types the frontend offers in the picker. Seed contains
  `market_entry` (enabled) and `ma` (disabled stub for V2).
  `alembic check` reports no drift; downgrade → upgrade round-trip
  verified.
- M3.2 — `Document` + `Chunk` ORM with pgvector HNSW index. Migration
  `0005_documents_and_chunks` creates the `document_status` Postgres
  enum, the `documents` and `chunks` tables, and the
  `ix_chunks_embedding_hnsw` HNSW index over `chunks.embedding` using
  `vector_cosine_ops`. Embedding dimension is sourced from
  `EMBEDDING_DIM` (default 1536) at migration time and from
  `Settings.embedding_dim` at ORM import time. The `Chunk.metadata_`
  Python attr maps to the `metadata` column to dodge the
  `DeclarativeBase.metadata` collision. Integration test
  `tests/integration/test_documents_orm.py::test_insert_document_and_chunk_roundtrip`
  exercises insert + read-back of a document plus a chunk with a random
  embedding vector. `alembic check` reports no drift; downgrade →
  upgrade round-trip clean and re-creates the HNSW index.

## Next Steps

1. M2.2 — runs / stages / artifacts tables (mirror the same one-class-per-file
   convention; remember to add each to `__init__.py`).
2. M2.4 — extend `SettingsService` with typed getters/setters for
   `SettingKV` keys (`max_stage_retries`, etc.) + Pydantic value validation.
3. Backfill a direct `User` test once any non-singleton row is created
   (e.g., by an `ensure_singleton_user()` helper).

## Known Issues / Blockers

- `SettingKV.value` is untyped JSONB; nothing prevents writing garbage
  shapes today. Mitigation lands with the service-layer validator (M2.4).
- The singleton user is seeded by migration `0002`. Any future migration
  that drops `users` must re-seed it (or rely on a startup hook). For V1
  there are no such migrations planned.
- `User.id` defaults to `uuid.uuid4`, but V1 only ever uses
  `SINGLETON_USER_ID`. Reading the default in code is a smell — callers
  should reference the constant.
- `ProviderKey.id` (UUID PK) is structurally redundant with the unique
  `(user_id, provider)` constraint. It exists so future API surfaces can
  reference a stable opaque id instead of `(user_id, provider)` tuples.
- `Chunk.embedding` is typed `vector(N)` with N evaluated at ORM import
  time from `Settings.embedding_dim`. Changing `EMBEDDING_DIM` at
  runtime does NOT resize the column — it requires a fresh migration
  (the migration also reads `EMBEDDING_DIM` at execution time) AND a
  backend restart so the model reflects the new dim. For V1 the dim is
  fixed at the embedding provider's native size (1536 for OpenAI
  text-embedding-3-small).

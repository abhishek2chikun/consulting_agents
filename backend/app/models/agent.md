# app.models — agent.md

## Status
**Active (M2.3).** Three ORM models landed: `User` (V1 single-row table),
`SettingKV` (per-user JSONB key/value store), and `ProviderKey`
(per-user Fernet-encrypted LLM provider API keys). Migrations `0002` and
`0003` create the underlying tables; `0002` also seeds the singleton user.

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
  __init__.py        # registry + re-exports (User, SettingKV, ProviderKey, SINGLETON_USER_ID)
  user.py            # User + SINGLETON_USER_ID constant
  settings_kv.py     # SettingKV (composite-PK JSONB store)
  provider_key.py    # ProviderKey (encrypted per-user provider API keys)
```

### Corresponding Tests
```text
backend/tests/integration/test_settings_kv.py
  test_upsert_and_read_setting   # exercises ON CONFLICT upsert + read-back
backend/tests/integration/test_settings_service.py
  test_set_provider_key_stores_encrypted     # raw column holds Fernet ciphertext, not plaintext
  test_get_provider_key_returns_plaintext    # round-trip + None for missing
  test_overwrite_provider_key_replaces_value # upsert keeps row count == 1
```

`User` has no dedicated test yet — it is exercised transitively via
`SettingKV.user_id` and `ProviderKey.user_id` FKs and the singleton seed
in migration `0002`.

---

## Public API

```python
from app.models import SINGLETON_USER_ID, ProviderKey, SettingKV, User

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
```

---

## Dependencies

| Imports from | What |
|---|---|
| `sqlalchemy` | `DateTime`, `ForeignKey`, `String`, `Text`, `UniqueConstraint`, `func` |
| `sqlalchemy.dialects.postgresql` | `UUID(as_uuid=True)`, `JSONB` |
| `sqlalchemy.orm` | `Mapped`, `mapped_column` |
| `app.core.db` | `Base` (DeclarativeBase) |

| Consumed by | What |
|---|---|
| `alembic/env.py` | indirectly — relies on `Base.metadata` being populated |
| `alembic/versions/0002_users_and_settings.py` | creates `users` + `settings_kv` |
| `alembic/versions/0003_provider_keys.py` | creates `provider_keys` |
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

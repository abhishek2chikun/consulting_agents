# app.services — agent.md

## Status
**Active (M3.3).** `SettingsService` owns encrypted provider-API-key
storage AND the JSON KV settings (model overrides, search provider,
max stage retries) used by the M2.4 REST API. `DocumentService` (M3.3)
owns the upload-on-disk + Document row lifecycle for the
`/documents` API; ingestion (parse → embed → ready/failed) lands in
M3.4+. Future milestones add `RunService`, `FramingService`, etc. — all
following the same shape (explicit `AsyncSession` injection, async
methods).

---

## Purpose

Thin domain services over the ORM. Each service:

- Takes an explicit `AsyncSession` in `__init__` — no hidden global session
  lookup. Callers (FastAPI route handlers in M2.4+, the agent runtime in
  later milestones) own the transaction scope and pass the session in.
- Exposes `async` methods only. The persistence layer is async; making
  the service sync would force `asyncio.run` calls at every call site.
- Validates inputs at the boundary and raises `ValueError` for bad
  user-controlled values.
- Owns crypto / encoding decisions for its data. Domain code outside the
  service should never see a Fernet token; ORM models hold ciphertext
  only.

V1 is single-user — services target `SINGLETON_USER_ID` implicitly. When
multi-user lands, signatures will change deliberately rather than
silently routing through whatever `user_id` callers happen to pass.

---

## Directory Structure
```text
app/services/
  __init__.py            # package marker (no re-exports yet)
  settings_service.py    # SettingsService — provider keys + JSON KV settings
  document_service.py    # DocumentService — upload binary + Document row lifecycle (M3.3)
```

### Corresponding Tests
```text
backend/tests/integration/test_settings_service.py
  test_set_provider_key_stores_encrypted     # raw column == Fernet ciphertext, never plaintext
  test_get_provider_key_returns_plaintext    # round-trip + None for missing provider
  test_overwrite_provider_key_replaces_value # ON CONFLICT keeps row count == 1
backend/tests/integration/test_settings_api.py
  # End-to-end coverage of get_setting / set_setting / list_provider_keys /
  # get_settings_snapshot via the REST API.
backend/tests/integration/test_documents_api.py
  # End-to-end coverage of DocumentService via the REST API
  # (upload writes file + creates pending row, list, delete, 404, empty-file 400).
```

---

## Public API

```python
from app.services.settings_service import (
    SettingsService,
    KNOWN_PROVIDERS,           # tuple[str, ...] — closed V1 provider list
    DEFAULT_MAX_STAGE_RETRIES, # int = 2
)

# SettingsService — single-user provider API key vault + JSON KV settings.
#   __init__(session: AsyncSession)
#
# Provider keys (encrypted-at-rest):
#   async set_provider_key(provider: str, key: str) -> None
#       Wraps `key` via app.core.crypto.wrap and upserts on
#       (SINGLETON_USER_ID, lower(strip(provider))). Both arguments must be
#       non-empty after normalization; otherwise ValueError. Commits.
#   async get_provider_key(provider: str) -> str | None
#       Returns the decrypted plaintext, or None if no row exists.
#       ValueError if `provider` is empty.
#   async list_provider_keys() -> list[str]
#       Sorted list of provider names that currently have a key (used by
#       GET /settings/providers to compute the has_key flags).
#
# JSON KV (settings_kv):
#   async get_setting(key: str) -> dict[str, Any] | None
#       Returns the JSONB value stored under key, or None.
#   async set_setting(key: str, value: dict[str, Any]) -> None
#       Upserts on (SINGLETON_USER_ID, key). Commits.
#
# Snapshot (frontend bootstrap):
#   async get_settings_snapshot() -> dict[str, Any]
#       Returns {providers, model_overrides, search_provider, max_stage_retries}
#       with defaults applied for unset keys (model_overrides={},
#       search_provider=None, max_stage_retries=DEFAULT_MAX_STAGE_RETRIES).
```

```python
from app.services.document_service import DocumentService

# DocumentService — single-user document upload lifecycle (M3.3).
#   __init__(session: AsyncSession)
#
#   async create_document(*, filename: str, mime: str, content: bytes) -> Document
#       Inserts a Document row with status=pending, flushes to populate
#       id, writes content to {Settings.upload_dir}/{id}, then commits.
#       File-write failure rolls back the in-flight row (no orphan).
#   async list_documents() -> list[Document]
#       Returns SINGLETON_USER_ID's documents ordered by created_at desc.
#   async get_document(doc_id: uuid.UUID) -> Document | None
#       Single-row lookup by primary key.
#   async delete_document(doc_id: uuid.UUID) -> bool
#       Deletes the row + commits, then unlinks the on-disk file
#       (missing_ok=True). Returns False if the row didn't exist.
```

---

## Dependencies

| Imports from | What |
|---|---|
| `sqlalchemy` | `select` |
| `sqlalchemy.dialects.postgresql` | `insert` (for `ON CONFLICT DO UPDATE`) |
| `sqlalchemy.ext.asyncio` | `AsyncSession` |
| `app.core` | `crypto.wrap` / `crypto.unwrap`, `config.get_settings` (DocumentService reads `upload_dir`) |
| `app.models` | `ProviderKey`, `SettingKV`, `Document`, `DocumentStatus`, `SINGLETON_USER_ID` |

| Consumed by | What |
|---|---|
| `tests/integration/test_settings_service.py` | encrypted-at-rest + upsert coverage |
| `tests/integration/test_settings_api.py` | exercised via the M2.4 REST API |
| `tests/integration/test_documents_api.py` | exercises DocumentService via the M3.3 REST API |
| `app.api.settings` (M2.4) | route handlers instantiate per-request |
| `app.api.documents` (M3.3) | route handlers instantiate per-request |
| Future agent LLM client (M2.5) | retrieves provider keys before invoking models |

---

## Config

`SettingsService`: none. Crypto key is read by `app.core.crypto` from
`Settings.fernet_key` on every wrap/unwrap call. The DB session is
injected by the caller — no service-side connection management.

`DocumentService`: reads `Settings.upload_dir` (env: `UPLOAD_DIR`,
default `Path("data/uploads")`) on every call via `get_settings()`.
Resolved relative to the process working directory (typically the
repo root when uvicorn is launched via the project Makefile). The
service ensures the directory exists before writing.

---

## Current Progress

- M2.3 — `SettingsService.set_provider_key` / `get_provider_key` over
  Fernet. Postgres `INSERT … ON CONFLICT (user_id, provider) DO UPDATE`
  for upsert, with `updated_at` advanced via `EXCLUDED.updated_at` so
  the column drifts forward on every overwrite. Three integration tests
  (incl. raw `SELECT` confirming the column never contains plaintext)
  pass against dockerised Postgres.
- M2.4 — Added `list_provider_keys`, `get_setting`, `set_setting`, and
  `get_settings_snapshot`. Plus module-level `KNOWN_PROVIDERS` (closed
  V1 list: anthropic, openai, google, aws, ollama, tavily, exa,
  perplexity) and `DEFAULT_MAX_STAGE_RETRIES = 2`. KV writes follow the
  same commit-inside semantics as `set_provider_key`. End-to-end
  coverage via `tests/integration/test_settings_api.py` (14 tests).
- M3.3 — `DocumentService` lands. Manages the upload-on-disk + DB row
  lifecycle for `/documents`. Ordering on create: insert → flush →
  write file → commit (file failure rolls back; no orphan row).
  Ordering on delete: delete row → commit → unlink file
  (`missing_ok=True`) — the DB is the source of truth, so a stranded
  file is acceptable; an orphaned row is not. End-to-end coverage via
  `tests/integration/test_documents_api.py` (5 tests).

## Next Steps

1. M2.5 — `app.agents.llm` consumes `get_provider_key` to build
   per-provider clients; that's where the per-provider model whitelist
   will live (intentionally not in this service).
2. Add `delete_provider_key` when the "remove key" UX needs it.
3. M3.4+ — extend `DocumentService` with state-transition helpers
   (`mark_parsing` / `mark_embedding` / `mark_ready` / `mark_failed`)
   driven by the ingestion pipeline.
4. Add `RunService`, `FramingService` per the V1 plan.

## Known Issues / Blockers

- **Single-user assumption is baked in.** Methods do NOT accept
  `user_id`. When multi-user support lands, every method signature
  changes. Callers that need to be portable across that change should
  not store a `SettingsService` instance long-term.
- No `delete_provider_key` yet — added when the settings API needs it.
- `set_provider_key` commits inside the method. If a future caller
  needs to bundle the write into a larger transaction, that's a
  signature change (`commit: bool = True` flag, or move the commit
  out entirely). Acceptable for current call sites (one-shot CLI / API
  request handlers).
- No accidental-decryption rate limiting or audit log. V1 is
  single-tenant local-first, so this is acceptable.
- Plaintext keys live in Python memory for the duration of one method
  call. We deliberately do not cache them — DB hits are cheap, and
  short plaintext dwell time is good security hygiene.

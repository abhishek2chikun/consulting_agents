# app.schemas — agent.md

## Status
**Active (M2.6).** Two modules landed: `settings.py` (Settings REST API
DTOs) and `ping.py` (`/ping` request/response DTOs). Future milestones
add per-domain schema modules (runs, documents, exports, ...) following
the same pattern: one module per API surface, named after the router it
backs.

---

## Purpose

Owns the request / response Pydantic models for the HTTP API. Keeping
schemas in their own package (rather than co-located with routers in
`app/api/`) gives non-API consumers — the agent runtime, future CLI
commands, websocket payload validation — a stable import target without
dragging FastAPI in transitively.

Validation rules (`Field(min_length=...)`, `Literal[...]` enums,
`ge`/`le` bounds) live HERE, at the boundary, not in the service layer.
This means malformed requests are rejected with `422` before any DB
session is opened — services receive only well-formed inputs.

---

## Directory Structure
```text
app/schemas/
  __init__.py        # package marker (no re-exports yet)
  settings.py        # Settings API DTOs (M2.4)
  ping.py            # /ping request/response DTOs (M2.6)
```

### Corresponding Tests

Schemas are exercised end-to-end through the integration tests of the
routers that consume them:

```text
backend/tests/integration/test_settings_api.py
  # Validation behavior (422 for empty key / unknown enum / out-of-range int)
  # is asserted via real HTTP round-trips, not unit-level Pydantic tests.
```

---

## Public API

```python
from app.schemas.settings import (
    ProviderInfo,                # {provider: str, has_key: bool}
    ProvidersResponse,           # GET /settings/providers payload
    SetProviderKeyRequest,       # PUT /settings/providers/{provider} body
    ModelOverride,               # {provider: str, model: str}
    ModelOverridesRequest,       # PUT /settings/model_overrides body
    SearchProviderName,          # Literal["tavily", "exa", "perplexity"]
    SearchProviderRequest,       # PUT /settings/search_provider body
    MaxStageRetriesRequest,      # PUT /settings/max_stage_retries body (int 1..5)
    SettingsSnapshot,            # GET /settings consolidated payload
)

from app.schemas.ping import (
    PingRequest,                 # {prompt: str (1..10_000), role: str = "framing"}
    PingResponse,                # {response: str, model: str, provider: str}
)
```

Provider key responses NEVER include raw key material; `ProviderInfo`
only carries a `has_key` boolean. This is the schema-level guarantee
backing the `test_get_providers_never_exposes_raw_key` defensive test.

---

## Dependencies

| Imports from | What |
|---|---|
| `pydantic` | `BaseModel`, `Field` |
| `typing` | `Literal` |

| Consumed by | What |
|---|---|
| `app.api.settings` | request body / response model wiring |
| `tests/integration/test_settings_api.py` | indirectly (via the API) |

---

## Config

None.

---

## Current Progress

- M2.4 — `settings.py` covers all six Settings API endpoints. The role
  keys in `ModelOverridesRequest.overrides` are intentionally
  open-ended for V1 (the agent runtime hasn't pinned its role set yet
  — that arrives in M5); each value is structurally validated as a
  `{provider, model}` pair.
- `SearchProviderName` is a closed `Literal` enum so callers can't
  persist garbage that the agent runtime would later have to defensively
  reject.
- M2.6 — `ping.py` adds `PingRequest` (prompt 1..10_000 chars,
  optional `role` defaulting to `"framing"`) and `PingResponse`
  (`response`, `model`, `provider`). The 10 000-char prompt ceiling is
  a defensive guardrail since `/ping` isn't meant to carry full agent
  prompts.

## Next Steps

1. M2.5 — extend with `RunCreateRequest`, `RunResponse`, `StageStatus`
   DTOs once the runs API lands.
2. Per-domain modules (`documents.py`, `exports.py`, ...) added as
   their routers ship.
3. Once roles are locked down (M5), tighten `ModelOverridesRequest` to
   a `Literal` role enum.

## Known Issues / Blockers

- No shared `BaseModel` configuration (e.g. `model_config =
  ConfigDict(extra="forbid")`). Default Pydantic behavior accepts and
  ignores unknown fields — adequate for V1, but a future change could
  flip to `extra="forbid"` to catch typos in client requests early.

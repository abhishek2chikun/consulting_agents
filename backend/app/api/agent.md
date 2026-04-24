# app.api — agent.md

## Status
**Active (M2.6).** Two routers landed: `settings.py` (mounted at
`/settings`) and `ping.py` (mounted at `/ping`). Future milestones add
`runs.py`, `documents.py`, `websocket.py`, etc. — each module exposes a
single `router = APIRouter(...)` that `app.main.create_app` mounts via
`include_router`.

---

## Purpose

HTTP surface of the backend. Each module here is a thin translation
layer: parse the request via `app.schemas.*` DTOs, delegate to a
service in `app.services.*`, return the appropriate status code.
Business logic does NOT live here.

Conventions:

- One file per logical resource. Filename matches the router prefix
  (`settings.py` -> `/settings`).
- Each module exports a single `router: APIRouter` with `prefix=` and
  `tags=` set; `app.main` mounts it.
- Dependencies are injected via `Annotated[T, Depends(...)]` aliases
  (e.g. `SessionDep`, `SettingsServiceDep`) so route signatures stay
  free of `Depends(...)` defaults (ruff `B008`).
- PUT-success responses use `204 No Content`. Validation errors fall
  through to FastAPI's automatic Pydantic `422` handling.
- GET responses declare `response_model=` so OpenAPI documents the
  exact payload and unintentional field leaks are caught at boundary.

---

## Directory Structure
```text
app/api/
  __init__.py        # package marker (no re-exports yet)
  settings.py        # Settings router — /settings + subpaths (M2.4)
  ping.py            # Ping router — POST /ping (M2.6)
```

### Corresponding Tests
```text
backend/tests/integration/test_settings_api.py
  test_get_providers_returns_has_key_flags
  test_put_provider_key_stores_encrypted
  test_put_provider_key_rejects_empty
  test_put_model_overrides_stores_map
  test_put_search_provider_accepts_known
  test_put_search_provider_rejects_unknown
  test_put_max_stage_retries_in_range
  test_put_max_stage_retries_rejects_out_of_range[0|-1|6|100]
  test_get_settings_snapshot_combines_state
  test_get_settings_snapshot_uses_defaults_when_unset
  test_get_providers_never_exposes_raw_key

backend/tests/integration/test_ping.py
  test_ping_returns_response
  test_ping_validates_prompt_length
  test_ping_400_when_no_key
  test_ping_501_when_aws
  test_ping_uses_role_param
  test_ping_default_role_is_framing
```

---

## Public API

```python
from app.api.settings import router as settings_router
from app.api.ping import router as ping_router

# Routes (mounted by app.main.create_app):
#   GET    /settings/providers          -> ProvidersResponse
#   PUT    /settings/providers/{provider}    body: SetProviderKeyRequest    -> 204
#   PUT    /settings/model_overrides         body: ModelOverridesRequest    -> 204
#   PUT    /settings/search_provider         body: SearchProviderRequest    -> 204
#   PUT    /settings/max_stage_retries       body: MaxStageRetriesRequest   -> 204
#   GET    /settings                    -> SettingsSnapshot
#   POST   /ping                              body: PingRequest              -> PingResponse
```

GET endpoints expose only `has_key: bool` flags for provider keys; raw
key material never leaves the server. This is asserted by
`test_get_providers_never_exposes_raw_key`.

`/ping` is a smoke-test endpoint that resolves a chat model for the
requested role (default `"framing"`) via `app.agents.get_chat_model`
and returns the echoed prompt + model + provider labels. Error
mapping: `ValueError` (missing key / unknown provider) -> `400`,
`NotImplementedError` (AWS Bedrock deferral) -> `501`.

---

## Dependencies

| Imports from | What |
|---|---|
| `fastapi` | `APIRouter`, `Depends`, `status` |
| `sqlalchemy.ext.asyncio` | `AsyncSession` (for the `SessionDep` alias) |
| `app.core.db` | `get_session` (DI) |
| `app.schemas.settings` | request / response DTOs |
| `app.schemas.ping` | `PingRequest`, `PingResponse` |
| `app.services.settings_service` | `SettingsService`, `KNOWN_PROVIDERS` |
| `app.agents.llm` | `get_chat_model`, `provider_name_for` (for `/ping`) |
| `langchain_core.messages` | `HumanMessage` (for `/ping` invocation) |

| Consumed by | What |
|---|---|
| `app.main.create_app` | `include_router(settings_router)` |
| `tests/integration/test_settings_api.py` | drives via httpx + ASGITransport |

---

## Config

None directly — depends on `app.core.config.Settings` transitively
through `app.core.db` and `app.services.settings_service`.

---

## Current Progress

- M2.4 — Settings router with six endpoints. Smoke-verified against a
  live uvicorn (`/openapi.json` reports all six paths registered).
  All 14 integration tests (covering the 7 spec-required behaviors,
  plus parametrized boundary cases and a defensive raw-key leak scan)
  pass against dockerised Postgres.
- M2.6 — `ping.py` router mounted at `/ping`. `POST /ping` resolves a
  chat model via `app.agents.get_chat_model(role, ...)` (default role
  `"framing"`), invokes it with the prompt as a `HumanMessage`, and
  returns `{response, model, provider}`. Errors map: missing key /
  unknown provider -> 400, AWS Bedrock deferral -> 501. Six
  integration tests in `test_ping.py` use a `FakeChatModel` injected
  via `monkeypatch.setattr(app.api.ping, "get_chat_model", ...)`. Live
  smoke (no key configured) returns the expected 400 with the
  `"No API key configured for provider 'anthropic'"` detail.

## Next Steps

1. M3 — `runs.py` for run creation / status / cancel.
2. M4 — websocket router for live stage updates.
3. Add a module-level `api_router = APIRouter()` aggregator if the set
   of subroutes grows beyond easy hand-mounting in `app.main`.

## Known Issues / Blockers

- No `DELETE /settings/providers/{provider}` yet. The "remove key" UX
  is not part of M2.4; will be added when the frontend needs it.
- No auth. V1 is single-user local-first; every request implicitly
  acts as `SINGLETON_USER_ID`. When auth lands, every route gains a
  `current_user: User = Depends(...)` and the service signatures
  change in lockstep.
- No rate limiting on the PUT endpoints. Acceptable given the
  single-tenant local-first deployment model.

# app.agents — agent.md

## Status
**Active (M3.7).** Hosts the LLM provider registry, the
`get_chat_model(role, *, session)` factory used by every downstream
agent node, the `provider_name_for(model)` helper that maps a
constructed LangChain client back to its registry key (consumed by
`app.api.ping` in M2.6), and (M3.7) the `tools/` subpackage of
`@tool`-decorated callables that agent nodes will bind to LLMs. V1
ships a single tool: `rag_search` (vector similarity over ingested
chunks). Future home of the LangGraph-based agent runtime (framing,
planning, retrieval, drafting, critique, packaging) and the
DeepAgents wiring.

---

## Purpose

`app.agents.llm` is the single resolution point between a *role*
identifier (e.g. `"framing"`, `"planner"`, `"drafter"`) and a concrete
LangChain `BaseChatModel`. It hides three concerns from callers:

1. **Per-role model overrides** stored in `settings_kv` under
   `model_overrides` (M2.4 schema).
2. **Encrypted-at-rest provider keys** retrieved via
   `SettingsService.get_provider_key`.
3. **Provider-specific construction** — each LangChain integration has
   its own constructor signature; the registry hides that.

Centralising resolution here means switching providers (or rotating a
key) is a settings update, never a code change.

---

## Directory Structure
```text
app/agents/
  __init__.py          # package marker
  llm.py               # PROVIDER_REGISTRY + get_chat_model factory
  tools/               # M3.7 — @tool-decorated callables (RAG, web search, ...)
    __init__.py
    rag_search.py      # @tool rag_search — pgvector cosine over chunks
    agent.md
```

### Corresponding Tests
```text
backend/tests/unit/test_llm_registry.py
  test_get_chat_model_uses_override
  test_get_chat_model_uses_default_when_no_override
  test_get_chat_model_raises_when_no_key
  test_get_chat_model_raises_on_unknown_provider
  test_get_chat_model_ollama_no_key_required
  test_get_chat_model_aws_not_implemented
  test_provider_registry_has_all_llm_providers
  test_get_chat_model_rejects_empty_role[|   ]   # parametrized over "" and "   "
```

All seven tests are pure unit tests — `SettingsService` and the
LangChain constructors are mocked so no DB / network / API key is
required. They run inside `make check`.

---

## Public API

```python
from app.agents import (        # re-exported from app.agents.llm
    PROVIDER_REGISTRY,   # dict[str, ProviderSpec]
    LLM_PROVIDERS,       # set[str] — registry keys, exported for validation
    DEFAULT_PROVIDER,    # str = "anthropic"
    get_chat_model,      # async (role, *, session) -> BaseChatModel
    provider_name_for,   # (model: BaseChatModel) -> str (e.g. "anthropic")
)
# `ProviderSpec` (TypedDict) lives in `app.agents.llm` if needed.
```

### Resolution order inside `get_chat_model`

1. Read `settings_kv["model_overrides"]["overrides"][role]`. If present
   and shaped `{"provider": str, "model": str}`, use it.
2. Otherwise fall back to `DEFAULT_PROVIDER` + that provider's
   `default_model`.
3. Validate `provider in PROVIDER_REGISTRY`; raise `ValueError("Unknown
   provider: …")` otherwise.
4. Fetch the API key. If `spec.requires_key` is True and the key is
   missing, raise `ValueError("No API key configured for provider …")`.
5. Call `spec.factory(model, key)` and return the chat model.

### Registry contents (V1)

| Provider | Default model | requires_key | Notes |
|---|---|---|---|
| `anthropic` | `claude-sonnet-4-5` | yes | V1 reference provider |
| `openai` | `gpt-4o` | yes | |
| `google` | `gemini-2.5-pro` | yes | passes key as `google_api_key=` |
| `aws` | `anthropic.claude-3-5-sonnet-20241022-v2:0` | yes | factory raises `NotImplementedError` (see Known Issues) |
| `ollama` | `llama3.2` | **no** | local runtime; key argument ignored |

---

## Dependencies

| Imports from | What |
|---|---|
| `langchain_core.language_models.chat_models` | `BaseChatModel` (return type) |
| `langchain_anthropic` | `ChatAnthropic` |
| `langchain_openai` | `ChatOpenAI` |
| `langchain_google_genai` | `ChatGoogleGenerativeAI` |
| `langchain_ollama` | `ChatOllama` |
| `sqlalchemy.ext.asyncio` | `AsyncSession` (parameter type) |
| `app.services.settings_service` | `SettingsService` |

| Consumed by | What |
|---|---|
| `tests.unit.test_llm_registry` | covers the 8 behaviors above |
| `app.api.ping` (M2.6) | smoke-test endpoint resolves a chat model and labels its provider via `provider_name_for` |
| Future: `app.agents.<role>.*` (M5+) | each role node calls `get_chat_model("<role>", session=...)` |

---

## Config

None at this layer. All configuration flows through `SettingsService`
(model overrides + encrypted provider keys). The factory is stateless
and constructs a fresh chat model on every call — see Known Issues
about caching.

---

## Current Progress

- M2.5 — Registry, factory, and seven unit tests landed. AWS Bedrock
  registered but explicitly unimplemented. Six new dependencies added
  to `backend/pyproject.toml` (langchain-core / -anthropic / -openai /
  -google-genai / -aws / -ollama). All quality gates green
  (`make check`, ruff, ruff-format, `mypy --strict app`).
- M2.6 — Three small additions: (1) `provider_name_for(model)` helper
  + `_CLASS_TO_PROVIDER` map, exported alongside the existing factory;
  (2) parametrized empty-role unit test (`""` and `"   "`) pinning the
  module-level guard; (3) `app/agents/__init__.py` now re-exports
  `get_chat_model`, `provider_name_for`, `PROVIDER_REGISTRY`,
  `LLM_PROVIDERS`, `DEFAULT_PROVIDER` so callers can write
  `from app.agents import ...` (mirrors `app.models`). Inline
  `# type: ignore[arg-type]` on `_openai_factory` now carries the same
  rationale comment as `_anthropic_factory`.
- M3.7 — New `app/agents/tools/` subpackage with `rag_search.py`. See
  `app/agents/tools/agent.md` for the full per-module rundown. Summary:
  `@tool`-decorated async function over the pgvector `Chunk.embedding`
  ORM comparator (`cosine_distance`); embeds the query via
  `app.ingestion.embedder.embed_texts`; returns `list[RagHit]` with
  `text / document_id / chunk_id / ord / score` (score = 1 - distance,
  higher better). Two unit tests (early-exit paths) + one live
  integration test (skipped without `OPENAI_API_KEY`).

## Next Steps

1. **M2.6** — surface the LLM provider list / per-role override UI in
   the frontend Settings panel (consumes `LLM_PROVIDERS`).
2. **M5** — wire `get_chat_model` into the LangGraph nodes for
   framing → planning → retrieval → drafting → critique →
   packaging. Each node selects its model by role string.
3. Add a `delete_provider_key` path to `SettingsService` once the
   settings UI grows a "remove key" affordance — `get_chat_model` will
   then surface the same `ValueError` for previously-configured
   providers.

## Known Issues / Blockers

- **AWS Bedrock is intentionally unimplemented.** Bedrock authenticates
  via access key + secret + region, not a single opaque token, and the
  V1 `provider_keys` schema only stores one string per provider.
  `_aws_factory` raises `NotImplementedError` with a clear message;
  V1.1 will either extend the key schema (JSON-encoded credential
  bundle) or rely on the boto3 default credential chain.
- **No model caching.** Every `get_chat_model` call rebuilds the
  underlying LangChain client. Construction is cheap, key rotation is
  immediate, and there's no cross-call cache that has to invalidate
  when settings change. Revisit if profiling shows construction
  overhead matters.
- **Type annotations on third-party constructors are loose.** A
  targeted `# type: ignore[arg-type,call-arg]` is needed on
  `ChatAnthropic` because its static signature requires `SecretStr`
  while pydantic happily coerces a plain `str` at runtime. Suppression
  is scoped to the single line and documented inline.
- **Default model identifiers will drift.** The V1 defaults are listed
  above; users override per-role via `model_overrides`. Refresh on
  major upstream releases.

# app.agents — agent.md

## Status
**Active (V1.6).** Hosts both the LLM/provider registry and the shared
consulting runtime used by `market_entry`, `pricing`, and
`profitability`. V1.6 adds `_engine/` modules for skill injection,
worker fanout, per-stage reviewer prompts, path normalization, and
stale-run recovery, alongside the existing tool subpackage.

---

## Purpose

`app.agents.llm` is still the single resolution point between a *role*
identifier (e.g. `"framing"`, `"research"`, `"reviewer"`) and a concrete
LangChain `BaseChatModel`, but the package now also hosts the shared
consulting engine:

1. **Profile-driven orchestration** in `_engine/` (`ConsultingProfile`,
   `ProfileStage`, `WorkerSpec`, graph builder, node builders).
2. **Skill injection** via `_engine.skills` (`load_skill`,
   `render_skills_block`, `inject_skills`).
3. **Worker fanout** via `_engine/nodes/stage.py`, with dotted worker
   agent ids and per-worker artifact/evidence merge.

The LLM registry itself hides three concerns from callers:

1. **Per-role model overrides** stored in `settings_kv` under
   `model_overrides` (M2.4 schema).
2. **Credential resolution** — encrypted provider keys from
   `SettingsService.get_provider_key`, Bedrock bearer keys, explicit AWS
   env credentials, or the boto3 default chain depending on provider.
3. **Provider-specific construction** — each LangChain integration has
   its own constructor signature; the registry hides that.

Centralising resolution here means switching providers (or rotating a
key) is a settings update, never a code change.

---

## Directory Structure
```text
app/agents/
  __init__.py
  llm.py               # PROVIDER_REGISTRY + get_chat_model factory
  _engine/
    __init__.py
    profile.py         # ConsultingProfile / ProfileStage / WorkerSpec
    registry.py        # PROFILE_REGISTRY + register/get helpers
    graph.py           # build_consulting_graph(...)
    skills.py          # SKILL.md loader + prompt injection helpers
    recovery.py        # stale-run recovery sweep
    paths.py           # read-side artifact path normalization
    nodes/
      framing.py
      stage.py         # ReAct loop + worker fanout
      reviewer.py      # base reviewer + stage addenda + skill injection
      synthesis.py
      audit.py
  market_entry/
  pricing/
  profitability/
  ma/
  budget.py
  tools/
    __init__.py
    cite.py
    rag_search.py
    web_search.py
    fetch_url.py
    read_doc.py
    write_artifact.py
    providers/
      base.py
      tavily.py
      exa.py
      perplexity.py
      duckduckgo.py
    agent.md
```

### Corresponding Tests
```text
backend/tests/unit/test_llm_registry.py
backend/tests/unit/test_skill_loader.py
backend/tests/unit/test_profile_extensions.py
backend/tests/unit/test_per_stage_max_retries.py
backend/tests/unit/test_path_normalization.py
backend/tests/integration/test_stage_node_react.py
backend/tests/integration/test_worker_fanout.py
backend/tests/integration/test_per_stage_reviewer.py
backend/tests/integration/test_run_recovery.py
backend/tests/integration/test_market_entry_v16_smoke.py
backend/tests/integration/test_pricing_v16_smoke.py
backend/tests/integration/test_profitability_v16_smoke.py
```

The registry tests remain pure unit tests. The V1.6 engine additions are
covered by a mix of unit and integration tests (tool loop, worker
fanout, reviewer prompt resolution, recovery, and profile smoke runs).

---

## Public API

```python
from app.agents import (        # re-exported from app.agents.llm
    PROVIDER_REGISTRY,   # dict[str, ProviderSpec]
    LLM_PROVIDERS,       # set[str] — registry keys, exported for validation
    DEFAULT_PROVIDER,    # str = "aws" in this worktree
    get_chat_model,      # async (role, *, session) -> BaseChatModel
    provider_name_for,   # (model: BaseChatModel) -> str (e.g. "anthropic")
)
from app.agents._engine import (
    PROFILE_REGISTRY,
    ConsultingProfile,
    ProfileStage,
    WorkerSpec,
    get_profile,
    register_profile,
)
```

### Resolution order inside `get_chat_model`

1. Read `settings_kv["model_overrides"]["overrides"][role]`. If present
   and shaped `{"provider": str, "model": str}`, use it.
2. Otherwise fall back to `DEFAULT_PROVIDER`. In this worktree that is
   `"aws"`, so the model comes from `_aws_default_model()`
   (`CLAUDE_MODEL` env, then `Settings.claude_model`, then the registry
   default). Non-AWS defaults use the provider registry's
   `default_model`.
3. Validate `provider in PROVIDER_REGISTRY`; raise `ValueError("Unknown
   provider: …")` otherwise.
4. Fetch the API key. If `spec.requires_key` is True and the key is
   missing, raise `ValueError("No API key configured for provider …")`.
5. Call `spec.factory(model, key)` and return the chat model.

### Shared engine (V1.6)

- `build_consulting_graph(profile, *, model_factory, ...)` compiles the
  profile-driven consulting runtime from the registered stage list.
- `_engine.__init__` re-exports `PROFILE_REGISTRY`, `register_profile`,
  and `get_profile` for profile discovery and registration.
- `stage.py` runs a bounded ReAct loop when tools are available and fans
  out to worker prompts when `stage.workers` is populated.
- `reviewer.py` composes the base reviewer rubric with stage-specific
  addenda and stage-specific skill injection.
- `skills.py` loads `app.skills/<slug>/SKILL.md`, strips frontmatter,
  caches the bodies, and prepends them to system prompts.
- `recovery.py` marks stale `running` rows failed at startup and emits
  `system.run_failed`.

### Registry contents

| Provider | Default model | requires_key | Notes |
|---|---|---|---|
| `anthropic` | `claude-sonnet-4-5` | yes | V1 reference provider |
| `openai` | `gpt-4o` | yes | |
| `google` | `gemini-2.5-pro` | yes | passes key as `google_api_key=` |
| `aws` | `us.anthropic.claude-haiku-4-5-20251001-v1:0` | no | supports Bedrock credential bundles and bearer-token fallback |
| `ollama` | `llama3.2` | **no** | local runtime; key argument ignored |

---

## Dependencies

| Imports from | What |
|---|---|
| `langchain_core.language_models.chat_models` | `BaseChatModel` |
| `langchain_anthropic` | `ChatAnthropic` |
| `langchain_openai` | `ChatOpenAI` |
| `langchain_google_genai` | `ChatGoogleGenerativeAI` |
| `langchain_ollama` | `ChatOllama` |
| `langchain_aws` | `ChatBedrockConverse` |
| `sqlalchemy.ext.asyncio` | `AsyncSession` (parameter type) |
| `app.services.settings_service` | `SettingsService` |
| `app.skills` | skill packs injected into prompts |

| Consumed by | What |
|---|---|
| `app.api.runs` | resolves per-run model factories for framing / worker execution |
| `app.workers.run_worker` | compiles consulting graphs and runs them in the background |
| `tests.unit.test_llm_registry` | covers provider/model resolution |
| `app.api.ping` (M2.6) | smoke-test endpoint resolves a chat model and labels its provider via `provider_name_for` |
| `app.agents.market_entry|pricing|profitability` | provide profile + prompts to the shared engine |

---

## Config

Configuration flows through `SettingsService` (model overrides +
encrypted provider keys) and `app.core.config.Settings` for runtime
knobs (`run_timeout_seconds`, `heartbeat_interval_seconds`,
`stale_run_threshold_seconds`, `worker_concurrency`,
`react_max_iterations`).

---

## Current Progress

- V1.6 ships the profile-driven consulting engine, worker fanout,
  per-stage reviewer prompts, skill injection, stale-run recovery, and
  smoke-tested worker pipelines for `market_entry`, `pricing`, and
  `profitability`.
- `get_chat_model()` now stamps production models explicitly so the
  production path can reject scripted/fake models if they somehow bypass
  dependency overrides.
- AWS Bedrock is no longer a stub: the factory supports per-call
  credential bundles, bearer-token fallback, and explicit production
  model marking.

## Next Steps

1. Keep the engine/docs/tests in sync as new consulting types or worker
   patterns are introduced.
2. Revisit provider attribution so usage telemetry does not rely on a
   class-name map.
3. Add delete/remove-key UX once the settings UI needs it.

## Known Issues / Blockers

- **No model caching.** Every `get_chat_model` call rebuilds the
  underlying LangChain client. Construction is cheap, key rotation is
  immediate, and there's no cross-call cache that has to invalidate
  when settings change. Revisit if profiling shows construction
  overhead matters.
- **Provider attribution still uses `_CLASS_TO_PROVIDER`.** That is good
  enough for V1.6 tests, but future wrappers/renames should move to an
  explicit provider field carried from registry resolution.
- **Type annotations on third-party constructors are loose.** A
  targeted `# type: ignore[arg-type,call-arg]` is needed on
  `ChatAnthropic` because its static signature requires `SecretStr`
  while pydantic happily coerces a plain `str` at runtime. Suppression
  is scoped to the single line and documented inline.
- **Default model identifiers will drift.** The V1 defaults are listed
  above; users override per-role via `model_overrides`. Refresh on
  major upstream releases.

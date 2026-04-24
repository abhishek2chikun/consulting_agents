"""LLM provider registry & `get_chat_model` factory.

This module is the single resolution point between an agent role
(string identifier such as `"framing"`, `"planner"`, etc.) and a
concrete LangChain `BaseChatModel` instance, configured with the
provider/model the user has chosen and authenticated with the
encrypted-at-rest API key managed by `SettingsService`.

Resolution order (per call):
    1. Look up `model_overrides[role]` from `settings_kv` via
       `SettingsService.get_setting("model_overrides")`. The stored
       shape is `{"overrides": {role: {"provider": ..., "model": ...}}}`.
    2. If no override exists for `role`, fall back to
       `DEFAULT_PROVIDER` and that provider's `default_model` from
       `PROVIDER_REGISTRY`.
    3. Validate the provider against `LLM_PROVIDERS`.
    4. Fetch the API key via `SettingsService.get_provider_key`.
       Providers with `requires_key=True` raise `ValueError` if the key
       is missing; providers with `requires_key=False` (Ollama) are
       constructed even without a stored key.
    5. Instantiate via `PROVIDER_REGISTRY[provider]["factory"](model, key)`.

V1 design notes:
- Models are NOT cached. LangChain chat-model construction is cheap;
  per-call instantiation keeps key rotation immediate and avoids a
  process-wide cache that would have to invalidate on settings updates.
- AWS Bedrock is registered but its factory raises
  `NotImplementedError`. Bedrock auth uses an access key + secret +
  region rather than a single opaque token; full support is deferred to
  V1.1. See `agent.md`.
- Default model identifiers favor `*-latest` aliases where the provider
  exposes them, so the registry doesn't drift behind upstream releases.
  These are user-overridable per-role via `model_overrides`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypedDict

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.settings_service import SettingsService


class ProviderSpec(TypedDict):
    """One row of `PROVIDER_REGISTRY`."""

    default_model: str
    factory: Callable[[str, str | None], BaseChatModel]
    requires_key: bool


def _anthropic_factory(model: str, key: str | None) -> BaseChatModel:
    # ChatAnthropic accepts SecretStr or str via pydantic coercion at runtime;
    # the static type annotation is narrower than the runtime contract.
    return ChatAnthropic(model=model, api_key=key)  # type: ignore[arg-type,call-arg]


def _openai_factory(model: str, key: str | None) -> BaseChatModel:
    # ChatOpenAI accepts SecretStr or str via pydantic coercion at runtime;
    # the static type annotation is narrower than the runtime contract.
    return ChatOpenAI(model=model, api_key=key)  # type: ignore[arg-type]


def _google_factory(model: str, key: str | None) -> BaseChatModel:
    return ChatGoogleGenerativeAI(model=model, google_api_key=key)


def _ollama_factory(model: str, key: str | None) -> BaseChatModel:
    # Ollama runs locally and authenticates via host URL, not API key.
    # The `key` argument is intentionally ignored.
    return ChatOllama(model=model)


def _aws_factory(model: str, key: str | None) -> BaseChatModel:
    # AWS Bedrock uses access_key + secret + region rather than a single
    # opaque token. Full support is deferred to V1.1; for V1 we register
    # the entry so settings UIs can list it, but instantiation fails
    # loudly so no caller ever silently gets the wrong client.
    raise NotImplementedError(
        "AWS Bedrock support deferred to V1.1 — Bedrock requires multi-part"
        " AWS credentials (access key + secret + region) which the V1"
        " single-key provider model does not yet express."
    )


PROVIDER_REGISTRY: dict[str, ProviderSpec] = {
    "anthropic": {
        "default_model": "claude-sonnet-4-5",
        "factory": _anthropic_factory,
        "requires_key": True,
    },
    "openai": {
        "default_model": "gpt-4o",
        "factory": _openai_factory,
        "requires_key": True,
    },
    "google": {
        "default_model": "gemini-2.5-pro",
        "factory": _google_factory,
        "requires_key": True,
    },
    "aws": {
        "default_model": "anthropic.claude-3-5-sonnet-20241022-v2:0",
        "factory": _aws_factory,
        "requires_key": True,
    },
    "ollama": {
        "default_model": "llama3.2",
        "factory": _ollama_factory,
        "requires_key": False,
    },
}

# Set of provider names valid for chat-model resolution. Mirrors the
# registry keys; exposed as a constant so callers can validate user
# input without poking at the registry directly.
LLM_PROVIDERS: set[str] = set(PROVIDER_REGISTRY.keys())

# Provider used when no `model_overrides[role]` entry exists. Anthropic
# is V1's reference provider (the agent's prompts and behavior were
# designed against Claude); other providers are best-effort.
DEFAULT_PROVIDER: str = "anthropic"


async def get_chat_model(role: str, *, session: AsyncSession) -> BaseChatModel:
    """Resolve a chat model for `role`.

    See module docstring for the full resolution order. Always returns
    a freshly-constructed `BaseChatModel`; no caching.

    Raises:
        ValueError: `role` is empty, the override references an unknown
            provider, or the chosen provider requires an API key but
            none is configured.
        NotImplementedError: provider is registered but instantiation is
            not yet implemented (currently only AWS Bedrock).
    """
    if not role or not role.strip():
        raise ValueError("role must be a non-empty string")

    service = SettingsService(session)

    overrides_row = await service.get_setting("model_overrides")
    overrides: dict[str, dict[str, str]] = {}
    if isinstance(overrides_row, dict):
        raw = overrides_row.get("overrides")
        if isinstance(raw, dict):
            overrides = raw

    role_override = overrides.get(role)
    if isinstance(role_override, dict) and "provider" in role_override and "model" in role_override:
        provider = str(role_override["provider"])
        model = str(role_override["model"])
    else:
        provider = DEFAULT_PROVIDER
        model = PROVIDER_REGISTRY[DEFAULT_PROVIDER]["default_model"]

    if provider not in PROVIDER_REGISTRY:
        raise ValueError(f"Unknown provider: {provider!r}")

    spec = PROVIDER_REGISTRY[provider]
    key = await service.get_provider_key(provider)
    if spec["requires_key"] and not key:
        raise ValueError(f"No API key configured for provider {provider!r}")

    return spec["factory"](model, key)


# Maps the LangChain chat-model class name back to the registry provider key.
# Used by callers (e.g. /ping) that need a clean provider label without
# re-deriving it from settings. Kept as a module-level constant so adding a
# new provider only requires touching one map.
_CLASS_TO_PROVIDER: dict[str, str] = {
    "ChatAnthropic": "anthropic",
    "ChatOpenAI": "openai",
    "ChatGoogleGenerativeAI": "google",
    "ChatBedrock": "aws",
    "ChatOllama": "ollama",
}


def provider_name_for(model: BaseChatModel) -> str:
    """Return the registry provider key for a constructed chat model.

    Returns ``"unknown"`` if the model's class is not in the registry —
    callers (e.g. tests with fake models) should treat this as a label,
    not a guarantee.
    """
    return _CLASS_TO_PROVIDER.get(type(model).__name__, "unknown")


__all__ = [
    "DEFAULT_PROVIDER",
    "LLM_PROVIDERS",
    "PROVIDER_REGISTRY",
    "ProviderSpec",
    "get_chat_model",
    "provider_name_for",
]

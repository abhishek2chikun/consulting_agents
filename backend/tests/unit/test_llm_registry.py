"""Unit tests for `app.agents.llm` — provider registry & `get_chat_model`.

These tests mock both `SettingsService` and the LangChain chat-model
constructors so they run without a database, network, or real API key.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import llm as llm_module
from app.agents.llm import (
    DEFAULT_PROVIDER,
    LLM_PROVIDERS,
    PROVIDER_REGISTRY,
    get_chat_model,
)


def _patch_service(
    monkeypatch: pytest.MonkeyPatch,
    *,
    overrides: dict[str, Any] | None,
    keys: dict[str, str | None],
) -> MagicMock:
    """Patch `SettingsService` inside `app.agents.llm` so that:

    - `get_setting("model_overrides")` returns `{"overrides": overrides}` when
      `overrides` is not None, else `None`.
    - `get_provider_key(name)` returns `keys.get(name)`.
    """
    service = MagicMock()

    async def _get_setting(key: str) -> dict[str, Any] | None:
        if key == "model_overrides" and overrides is not None:
            return {"overrides": overrides}
        return None

    async def _get_provider_key(provider: str) -> str | None:
        return keys.get(provider)

    service.get_setting = AsyncMock(side_effect=_get_setting)
    service.get_provider_key = AsyncMock(side_effect=_get_provider_key)

    monkeypatch.setattr(llm_module, "SettingsService", lambda session: service)
    return service


@pytest.mark.asyncio
async def test_get_chat_model_uses_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """An explicit `model_overrides[role]` entry wins over the registry default."""
    _patch_service(
        monkeypatch,
        overrides={"framing": {"provider": "anthropic", "model": "claude-3-5-haiku-latest"}},
        keys={"anthropic": "sk-test"},
    )
    constructor = MagicMock(return_value="chat-model-instance")
    monkeypatch.setattr(llm_module, "ChatAnthropic", constructor)

    session = MagicMock(spec=AsyncSession)
    result = await get_chat_model("framing", session=session)

    assert result == "chat-model-instance"
    constructor.assert_called_once_with(model="claude-3-5-haiku-latest", api_key="sk-test")


@pytest.mark.asyncio
async def test_get_chat_model_uses_default_when_no_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Falls back to DEFAULT_PROVIDER + provider's default_model when no override."""
    _patch_service(
        monkeypatch,
        overrides=None,
        keys={"anthropic": "sk-default"},
    )
    constructor = MagicMock(return_value="default-model")
    monkeypatch.setattr(llm_module, "ChatAnthropic", constructor)

    session = MagicMock(spec=AsyncSession)
    result = await get_chat_model("framing", session=session)

    assert result == "default-model"
    expected_model = PROVIDER_REGISTRY[DEFAULT_PROVIDER]["default_model"]
    constructor.assert_called_once_with(model=expected_model, api_key="sk-default")


@pytest.mark.asyncio
async def test_get_chat_model_raises_when_no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provider requires a key but none is configured -> ValueError."""
    _patch_service(monkeypatch, overrides=None, keys={"anthropic": None})

    session = MagicMock(spec=AsyncSession)
    with pytest.raises(ValueError, match="No API key configured for provider 'anthropic'"):
        await get_chat_model("framing", session=session)


@pytest.mark.asyncio
async def test_get_chat_model_raises_on_unknown_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Override referencing an unknown provider -> ValueError."""
    _patch_service(
        monkeypatch,
        overrides={"framing": {"provider": "nonexistent", "model": "mystery"}},
        keys={},
    )

    session = MagicMock(spec=AsyncSession)
    with pytest.raises(ValueError, match="Unknown provider"):
        await get_chat_model("framing", session=session)


@pytest.mark.asyncio
async def test_get_chat_model_ollama_no_key_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ollama factory must succeed even with no stored API key."""
    _patch_service(
        monkeypatch,
        overrides={"framing": {"provider": "ollama", "model": "llama3.2"}},
        keys={"ollama": None},
    )
    constructor = MagicMock(return_value="ollama-instance")
    monkeypatch.setattr(llm_module, "ChatOllama", constructor)

    session = MagicMock(spec=AsyncSession)
    result = await get_chat_model("framing", session=session)

    assert result == "ollama-instance"
    constructor.assert_called_once()
    # Model must be forwarded; key argument is provider-specific (ollama ignores it).
    call_kwargs = constructor.call_args.kwargs
    assert call_kwargs.get("model") == "llama3.2"


@pytest.mark.asyncio
async def test_get_chat_model_aws_not_implemented(monkeypatch: pytest.MonkeyPatch) -> None:
    """AWS Bedrock support is deferred; the factory must raise NotImplementedError."""
    _patch_service(
        monkeypatch,
        overrides={
            "framing": {
                "provider": "aws",
                "model": "anthropic.claude-3-5-sonnet-20241022-v2:0",
            }
        },
        keys={"aws": "some-blob"},
    )

    session = MagicMock(spec=AsyncSession)
    with pytest.raises(NotImplementedError, match="AWS Bedrock"):
        await get_chat_model("framing", session=session)


def test_provider_registry_has_all_llm_providers() -> None:
    """The registry must cover exactly the V1 LLM provider set."""
    assert set(PROVIDER_REGISTRY.keys()) == {"anthropic", "openai", "google", "aws", "ollama"}
    assert LLM_PROVIDERS == set(PROVIDER_REGISTRY.keys())
    assert DEFAULT_PROVIDER in LLM_PROVIDERS


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_role", ["", "   "])
async def test_get_chat_model_rejects_empty_role(bad_role: str) -> None:
    """An empty/whitespace role string must be rejected before any DB I/O."""
    session = MagicMock(spec=AsyncSession)
    with pytest.raises(ValueError, match="non-empty"):
        await get_chat_model(bad_role, session=session)

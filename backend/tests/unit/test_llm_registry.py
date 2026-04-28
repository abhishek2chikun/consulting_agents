"""Unit tests for `app.agents.llm` — provider registry & `get_chat_model`.

These tests mock both `SettingsService` and the LangChain chat-model
constructors so they run without a database, network, or real API key.
"""

from __future__ import annotations

from types import SimpleNamespace
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


class _StubChatModel:
    pass


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
    monkeypatch.setattr(
        llm_module,
        "get_settings",
        lambda: SimpleNamespace(
            aws_region="us-east-1",
            bedrock_api_key="",
            claude_model=PROVIDER_REGISTRY[DEFAULT_PROVIDER]["default_model"],
            llm_timeout_sec=300,
            llm_max_tokens=16000,
        ),
    )
    return service


@pytest.mark.asyncio
async def test_get_chat_model_uses_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """An explicit `model_overrides[role]` entry wins over the registry default."""
    _patch_service(
        monkeypatch,
        overrides={"framing": {"provider": "anthropic", "model": "claude-3-5-haiku-latest"}},
        keys={"anthropic": "sk-test"},
    )
    model = _StubChatModel()
    constructor = MagicMock(return_value=model)
    monkeypatch.setattr(llm_module, "ChatAnthropic", constructor)

    session = MagicMock(spec=AsyncSession)
    result = await get_chat_model("framing", session=session)

    assert result is model
    assert getattr(result, llm_module.PRODUCTION_MODEL_MARKER) is True
    constructor.assert_called_once_with(model="claude-3-5-haiku-latest", api_key="sk-test")


@pytest.mark.asyncio
async def test_get_chat_model_uses_default_when_no_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Falls back to DEFAULT_PROVIDER + provider's default_model when no override.

    DEFAULT_PROVIDER is now ``"aws"`` which uses ChatBedrockConverse.
    We mock the factory so no real boto3 call is made.
    """
    _patch_service(
        monkeypatch,
        overrides=None,
        keys={"aws": None},  # aws requires_key=False, key value irrelevant
    )
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("BEDROCK_API_KEY", raising=False)
    monkeypatch.setenv("CLAUDE_MODEL", PROVIDER_REGISTRY[DEFAULT_PROVIDER]["default_model"])
    model = _StubChatModel()
    constructor = MagicMock(return_value=model)
    monkeypatch.setattr(llm_module, "ChatBedrockConverse", constructor)

    session = MagicMock(spec=AsyncSession)
    result = await get_chat_model("framing", session=session)

    assert result is model
    assert getattr(result, llm_module.PRODUCTION_MODEL_MARKER) is True
    # The factory passes model= and region_name= (at minimum).
    call_kwargs = constructor.call_args.kwargs
    assert call_kwargs.get("model") == PROVIDER_REGISTRY[DEFAULT_PROVIDER]["default_model"]


@pytest.mark.asyncio
async def test_get_chat_model_raises_when_no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provider requires a key but none is configured -> ValueError.

    Use an explicit anthropic override (requires_key=True) to exercise
    the missing-key guard — aws is now requires_key=False so it won't raise.
    """
    _patch_service(
        monkeypatch,
        overrides={"framing": {"provider": "anthropic", "model": "claude-3-5-haiku-latest"}},
        keys={"anthropic": None},
    )

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
    model = _StubChatModel()
    constructor = MagicMock(return_value=model)
    monkeypatch.setattr(llm_module, "ChatOllama", constructor)

    session = MagicMock(spec=AsyncSession)
    result = await get_chat_model("framing", session=session)

    assert result is model
    assert getattr(result, llm_module.PRODUCTION_MODEL_MARKER) is True
    constructor.assert_called_once()
    # Model must be forwarded; key argument is provider-specific (ollama ignores it).
    call_kwargs = constructor.call_args.kwargs
    assert call_kwargs.get("model") == "llama3.2"


@pytest.mark.asyncio
async def test_get_chat_model_aws_constructs_bedrock_converse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AWS Bedrock factory is now implemented via ChatBedrockConverse."""
    _patch_service(
        monkeypatch,
        overrides={
            "framing": {
                "provider": "aws",
                "model": "us.anthropic.claude-haiku-3-5-20241022-v1:0",
            }
        },
        keys={"aws": None},  # requires_key=False; env vars supply real creds
    )
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("BEDROCK_API_KEY", raising=False)
    model = _StubChatModel()
    constructor = MagicMock(return_value=model)
    monkeypatch.setattr(llm_module, "ChatBedrockConverse", constructor)

    session = MagicMock(spec=AsyncSession)
    result = await get_chat_model("framing", session=session)

    assert result is model
    assert getattr(result, llm_module.PRODUCTION_MODEL_MARKER) is True
    # Factory must forward the model id.
    call_kwargs = constructor.call_args.kwargs
    assert call_kwargs.get("model") == "us.anthropic.claude-haiku-3-5-20241022-v1:0"


@pytest.mark.asyncio
async def test_get_chat_model_aws_uses_bearer_bedrock_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-credential BEDROCK_API_KEY uses direct Bearer-token Bedrock HTTP."""
    _patch_service(
        monkeypatch,
        overrides={
            "framing": {
                "provider": "aws",
                "model": "us.anthropic.claude-haiku-3-5-20241022-v1:0",
            }
        },
        keys={"aws": "bedrock:api-key"},
    )
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.setenv("AWS_REGION", "us-west-2")

    session = MagicMock(spec=AsyncSession)
    result = await get_chat_model("framing", session=session)

    assert type(result).__name__ == "_BedrockBearerChatModel"
    assert result.model == "us.anthropic.claude-haiku-3-5-20241022-v1:0"
    assert result.region_name == "us-west-2"
    assert result.timeout_sec == 300
    assert result.max_tokens == 16000
    assert llm_module.provider_name_for(result) == "aws"


@pytest.mark.asyncio
async def test_get_chat_model_aws_bearer_uses_configured_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bearer-token Bedrock calls use the app-level LLM timeout setting."""
    _patch_service(
        monkeypatch,
        overrides={
            "research": {
                "provider": "aws",
                "model": "us.anthropic.claude-haiku-3-5-20241022-v1:0",
            }
        },
        keys={"aws": "bedrock:api-key"},
    )
    monkeypatch.setattr(
        llm_module,
        "get_settings",
        lambda: SimpleNamespace(
            aws_region="us-east-1",
            bedrock_api_key="",
            claude_model=PROVIDER_REGISTRY[DEFAULT_PROVIDER]["default_model"],
            llm_timeout_sec=900,
            llm_max_tokens=24000,
        ),
    )
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)

    session = MagicMock(spec=AsyncSession)
    result = await get_chat_model("research", session=session)

    assert type(result).__name__ == "_BedrockBearerChatModel"
    assert result.timeout_sec == 900
    assert result.max_tokens == 24000


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

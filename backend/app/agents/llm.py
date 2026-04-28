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

import base64
import json
import os
from collections.abc import Callable
from typing import Any, TypedDict

import httpx
from langchain_anthropic import ChatAnthropic
from langchain_aws import ChatBedrockConverse
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from pydantic import Field, SecretStr, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services.settings_service import SettingsService

PRODUCTION_MODEL_MARKER = "__production_model__"

_BEDROCK_MODEL_MAP: dict[str, str] = {
    "claude-haiku-4-5-20251001": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "claude-sonnet-4-20250514": "us.anthropic.claude-sonnet-4-20250514-v1:0",
}

_DEFAULT_AWS_MODEL = "us.anthropic.claude-haiku-4-5-20251001-v1:0"


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


def _aws_region() -> str:
    return os.environ.get("AWS_REGION") or get_settings().aws_region or "us-east-1"


def _aws_default_model() -> str:
    model = os.environ.get("CLAUDE_MODEL") or get_settings().claude_model or _DEFAULT_AWS_MODEL
    return _BEDROCK_MODEL_MAP.get(model, model)


def _bedrock_api_key(key: str | None) -> str:
    return key or os.environ.get("BEDROCK_API_KEY") or get_settings().bedrock_api_key


def _looks_like_aws_access_key_id(value: str) -> bool:
    return value.startswith(("AKIA", "ASIA")) and len(value) >= 16


def _aws_credentials_from_bedrock_key(raw_key: str) -> tuple[str, str] | None:
    """Extract ``(access_key_id, secret_access_key)`` from known key bundles."""
    access_key_id: str | None = None
    secret_access_key: str | None = None

    try:
        blob = base64.b64decode(raw_key + "==")
        start = 0
        for i, b in enumerate(blob):
            if 0x41 <= b <= 0x7A:  # first printable ASCII letter
                start = i
                break
        content = blob[start:].decode("utf-8")
        parts = content.split(":", 1)
        if len(parts) == 2 and _looks_like_aws_access_key_id(parts[0]) and parts[1]:
            access_key_id, secret_access_key = parts[0], parts[1]
    except Exception:
        pass

    if not access_key_id:
        parts = raw_key.split(":", 1)
        if len(parts) == 2 and _looks_like_aws_access_key_id(parts[0]) and parts[1]:
            access_key_id, secret_access_key = parts[0], parts[1]

    if access_key_id and secret_access_key:
        return access_key_id, secret_access_key
    return None


def _coerce_message_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            else:
                parts.append(str(item))
        return "\n".join(part for part in parts if part)
    return str(content)


def _extract_json_object(text: str) -> Any:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            return json.loads(stripped[start : end + 1])
        raise


class _BedrockBearerStructuredOutput:
    def __init__(self, model: _BedrockBearerChatModel, schema: Any) -> None:
        self._model = model
        self._schema = schema

    def _structured_messages(self, messages: list[BaseMessage]) -> list[BaseMessage]:
        schema_json = "{}"
        if hasattr(self._schema, "model_json_schema"):
            schema_json = json.dumps(self._schema.model_json_schema(), indent=2)

        instruction = (
            "Return only a valid JSON object matching this JSON Schema. "
            "Do not wrap it in Markdown or add explanatory text.\n\n"
            f"{schema_json}"
        )
        return [*messages, HumanMessage(content=instruction)]

    def _parse(self, text: str, *, stop_reason: str | None = None) -> Any:
        try:
            data = _extract_json_object(text)
            if hasattr(self._schema, "model_validate"):
                return self._schema.model_validate(data)
            return data
        except (json.JSONDecodeError, ValidationError) as exc:
            snippet = text.strip().replace("\n", " ")[:500]
            stop_context = f" stop_reason={stop_reason!r};" if stop_reason else ""
            raise ValueError(
                "AWS Bedrock structured output did not match the expected schema;"
                f"{stop_context} "
                f"response starts with: {snippet!r}"
            ) from exc

    def invoke(self, messages: list[BaseMessage], **kwargs: Any) -> Any:
        result = self._model.invoke(self._structured_messages(messages), **kwargs)
        text = result.content if isinstance(result.content, str) else str(result.content)
        return self._parse(text, stop_reason=result.response_metadata.get("stop_reason"))

    async def ainvoke(self, messages: list[BaseMessage], **kwargs: Any) -> Any:
        result = await self._model.ainvoke(self._structured_messages(messages), **kwargs)
        text = result.content if isinstance(result.content, str) else str(result.content)
        return self._parse(text, stop_reason=result.response_metadata.get("stop_reason"))


class _BedrockBearerChatModel(BaseChatModel):
    """Minimal Bedrock Runtime chat model for API-key Bearer auth."""

    model: str
    api_key: str = Field(repr=False)
    region_name: str = "us-east-1"
    max_tokens: int = 4096
    temperature: float = 0.2
    timeout_sec: int = 300

    @property
    def _llm_type(self) -> str:
        return "bedrock-bearer"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"model": self.model, "region_name": self.region_name}

    def _endpoint(self) -> str:
        return f"https://bedrock-runtime.{self.region_name}.amazonaws.com/model/{self.model}/invoke"

    def _payload(self, messages: list[BaseMessage], **kwargs: Any) -> dict[str, Any]:
        system_parts: list[str] = []
        bedrock_messages: list[dict[str, str]] = []

        for message in messages:
            content = _coerce_message_content(message.content)
            if message.type == "system":
                system_parts.append(content)
                continue

            role = "assistant" if message.type == "ai" else "user"
            if bedrock_messages and bedrock_messages[-1]["role"] == role:
                bedrock_messages[-1]["content"] += f"\n\n{content}"
            else:
                bedrock_messages.append({"role": role, "content": content})

        if not bedrock_messages:
            bedrock_messages.append({"role": "user", "content": ""})

        payload: dict[str, Any] = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": int(kwargs.get("max_tokens", self.max_tokens)),
            "messages": bedrock_messages,
            "temperature": float(kwargs.get("temperature", self.temperature)),
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)
        if stop := kwargs.get("stop"):
            payload["stop_sequences"] = stop
        return payload

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _chat_result(self, data: dict[str, Any]) -> ChatResult:
        text_parts = [
            block.get("text", "")
            for block in data.get("content", [])
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        if not text_parts and data.get("content"):
            text_parts = [str(data["content"])]
        message = AIMessage(
            content="".join(text_parts),
            response_metadata={
                "model": self.model,
                "usage": data.get("usage", {}),
                "stop_reason": data.get("stop_reason"),
            },
        )
        return ChatResult(generations=[ChatGeneration(message=message)])

    def _generate(  # type: ignore[override]
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        payload = self._payload(messages, stop=stop, **kwargs)
        try:
            with httpx.Client(timeout=self.timeout_sec) as client:
                response = client.post(self._endpoint(), headers=self._headers(), json=payload)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise TimeoutError(
                f"AWS Bedrock request timed out after {self.timeout_sec} seconds"
            ) from exc
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:500]
            raise RuntimeError(
                f"AWS Bedrock request failed with HTTP {exc.response.status_code}: {body}"
            ) from exc
        return self._chat_result(response.json())

    async def _agenerate(  # type: ignore[override]
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        payload = self._payload(messages, stop=stop, **kwargs)
        try:
            async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                response = await client.post(
                    self._endpoint(),
                    headers=self._headers(),
                    json=payload,
                )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise TimeoutError(
                f"AWS Bedrock request timed out after {self.timeout_sec} seconds"
            ) from exc
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:500]
            raise RuntimeError(
                f"AWS Bedrock request failed with HTTP {exc.response.status_code}: {body}"
            ) from exc
        return self._chat_result(response.json())

    def with_structured_output(  # type: ignore[override]
        self, schema: Any, **_: Any
    ) -> _BedrockBearerStructuredOutput:
        return _BedrockBearerStructuredOutput(self, schema)


def _aws_factory(model: str, key: str | None) -> BaseChatModel:
    """Construct a ChatBedrockConverse model.

    Credential resolution order (highest priority first):

    1. ``AWS_ACCESS_KEY_ID`` + ``AWS_SECRET_ACCESS_KEY`` already in env
        → boto3's default credential chain handles it automatically.
    2. ``BEDROCK_API_KEY`` in env — if it is an AWS credential bundle,
        blob produced by the AWS toolkit. The parsed access key + secret
        are passed directly to ``ChatBedrockConverse`` for this call only.
    3. ``BEDROCK_API_KEY`` as an API key → direct Bedrock Runtime HTTP with
        ``Authorization: Bearer ...``.
    4. Neither → ChatBedrockConverse is created without explicit creds;
        boto3 will try instance-profile / SSO / etc.

    ``AWS_REGION`` sets the region (default ``us-east-1``).
    The ``key`` argument (from the encrypted provider_keys table) is used
    as the Bedrock API key when present; otherwise ``BEDROCK_API_KEY`` is
    used.
    """
    region = _aws_region()
    bedrock_model = _BEDROCK_MODEL_MAP.get(model, model)
    settings = get_settings()
    timeout_sec = settings.llm_timeout_sec
    max_tokens = settings.llm_max_tokens

    # If standard IAM env vars are already present, let boto3 use them.
    if os.environ.get("AWS_ACCESS_KEY_ID"):
        return ChatBedrockConverse(model=bedrock_model, region_name=region)

    raw_key = _bedrock_api_key(key)
    if raw_key:
        credentials = _aws_credentials_from_bedrock_key(raw_key)
        if credentials is not None:
            access_key_id, secret_access_key = credentials
            return ChatBedrockConverse(
                model=bedrock_model,
                region_name=region,
                aws_access_key_id=SecretStr(access_key_id),
                aws_secret_access_key=SecretStr(secret_access_key),
            )

        return _BedrockBearerChatModel(
            model=bedrock_model,
            api_key=raw_key,
            region_name=region,
            timeout_sec=timeout_sec,
            max_tokens=max_tokens,
        )

    return ChatBedrockConverse(model=bedrock_model, region_name=region)


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
        # Cross-region inference profile for Claude Haiku (us-east-1).
        # Credentials come from BEDROCK_API_KEY + AWS_REGION env vars,
        # not the encrypted provider_keys table, so requires_key=False.
        "default_model": _DEFAULT_AWS_MODEL,
        "factory": _aws_factory,
        "requires_key": False,
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

# Provider used when no `model_overrides[role]` entry exists.
# Switched to "aws" for Bedrock-backed end-to-end testing; revert to
# "anthropic" once a direct Anthropic key is configured.
DEFAULT_PROVIDER: str = "aws"


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
        model = (
            _aws_default_model()
            if DEFAULT_PROVIDER == "aws"
            else PROVIDER_REGISTRY[DEFAULT_PROVIDER]["default_model"]
        )

    if provider not in PROVIDER_REGISTRY:
        raise ValueError(f"Unknown provider: {provider!r}")

    spec = PROVIDER_REGISTRY[provider]
    key = await service.get_provider_key(provider)
    if spec["requires_key"] and not key:
        raise ValueError(f"No API key configured for provider {provider!r}")

    resolved = spec["factory"](model, key)
    setattr(resolved, PRODUCTION_MODEL_MARKER, True)
    return resolved


# Maps the LangChain chat-model class name back to the registry provider key.
# Used by callers (e.g. /ping) that need a clean provider label without
# re-deriving it from settings. Kept as a module-level constant so adding a
# new provider only requires touching one map.
_CLASS_TO_PROVIDER: dict[str, str] = {
    "ChatAnthropic": "anthropic",
    "ChatOpenAI": "openai",
    "ChatGoogleGenerativeAI": "google",
    "ChatBedrock": "aws",
    "ChatBedrockConverse": "aws",
    "_BedrockBearerChatModel": "aws",
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
    "PRODUCTION_MODEL_MARKER",
    "PROVIDER_REGISTRY",
    "ProviderSpec",
    "get_chat_model",
    "provider_name_for",
]

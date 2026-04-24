"""Integration tests for the `/ping` endpoint (M2.6).

These tests drive the FastAPI app via httpx + ASGITransport (mirroring
`test_settings_api.py`) and patch `app.api.ping.get_chat_model` with a
fake `BaseChatModel` that returns deterministic text. No real LLM API
or network call is made.

Coverage:
- 200 happy path returns the echoed prompt + model + provider labels.
- Empty prompt is rejected at the schema boundary (422).
- Missing API key surfaces as 400 (not 500).
- AWS Bedrock NotImplementedError surfaces as 501.
- The `role` field is forwarded to `get_chat_model`.
- The default role is "framing" when omitted.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx
import pytest
from cryptography.fernet import Fernet
from langchain_core.messages import AIMessage

from app.api import ping as ping_module
from app.core.config import get_settings
from app.main import create_app


class FakeChatModel:
    """Minimal `BaseChatModel`-shaped fake for `/ping` integration tests.

    Only the surface `/ping` actually touches is implemented: the
    `model` attribute (used to derive the response label) and an async
    `ainvoke` returning an `AIMessage`. This intentionally does NOT
    inherit from `BaseChatModel` to keep the fake free of the abstract
    method burden — `/ping` only does duck-typed access.
    """

    model = "fake-model-v1"

    async def ainvoke(self, messages: list[Any], **_: Any) -> AIMessage:
        prompt = messages[0].content if messages else ""
        return AIMessage(content=f"echo: {prompt}")


@pytest.fixture(autouse=True)
def _fernet_key(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    # Required because `create_app` -> `get_settings()` validates env at import.
    monkeypatch.setenv("FERNET_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _patch_get_chat_model(
    monkeypatch: pytest.MonkeyPatch,
    *,
    factory: Any,
) -> list[dict[str, Any]]:
    """Replace `app.api.ping.get_chat_model` with a recording wrapper.

    Returns a list that will be appended to with the kwargs of every
    call, so tests can assert on `role=` forwarding.
    """
    calls: list[dict[str, Any]] = []

    async def _fake_get_chat_model(role: str, *, session: Any) -> Any:
        calls.append({"role": role, "session": session})
        return await factory(role)

    monkeypatch.setattr(ping_module, "get_chat_model", _fake_get_chat_model)
    return calls


async def test_ping_returns_response(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _factory(_role: str) -> FakeChatModel:
        return FakeChatModel()

    _patch_get_chat_model(monkeypatch, factory=_factory)

    resp = await client.post("/ping", json={"prompt": "hello"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["response"] == "echo: hello"
    assert body["model"] == "fake-model-v1"
    # FakeChatModel is not in _CLASS_TO_PROVIDER, so provider_name_for -> "unknown".
    assert body["provider"] == "unknown"


async def test_ping_validates_prompt_length(client: httpx.AsyncClient) -> None:
    resp = await client.post("/ping", json={"prompt": ""})
    assert resp.status_code == 422


async def test_ping_400_when_no_key(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _factory(_role: str) -> FakeChatModel:
        raise ValueError("No API key configured for provider 'anthropic'")

    _patch_get_chat_model(monkeypatch, factory=_factory)

    resp = await client.post("/ping", json={"prompt": "hi"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "No API key configured for provider 'anthropic'"


async def test_ping_501_when_aws(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _factory(_role: str) -> FakeChatModel:
        raise NotImplementedError("AWS Bedrock support deferred to V1.1")

    _patch_get_chat_model(monkeypatch, factory=_factory)

    resp = await client.post("/ping", json={"prompt": "hi"})
    assert resp.status_code == 501
    assert "AWS Bedrock" in resp.json()["detail"]


async def test_ping_uses_role_param(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _factory(_role: str) -> FakeChatModel:
        return FakeChatModel()

    calls = _patch_get_chat_model(monkeypatch, factory=_factory)

    resp = await client.post("/ping", json={"prompt": "x", "role": "research"})
    assert resp.status_code == 200, resp.text
    assert len(calls) == 1
    assert calls[0]["role"] == "research"


async def test_ping_default_role_is_framing(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _factory(_role: str) -> FakeChatModel:
        return FakeChatModel()

    calls = _patch_get_chat_model(monkeypatch, factory=_factory)

    resp = await client.post("/ping", json={"prompt": "x"})
    assert resp.status_code == 200, resp.text
    assert len(calls) == 1
    assert calls[0]["role"] == "framing"

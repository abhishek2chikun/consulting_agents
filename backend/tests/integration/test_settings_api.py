"""Integration tests for the Settings REST API (M2.4).

Drives the FastAPI app via httpx + ASGITransport (no live network),
backed by the real Postgres instance brought up via `make db-up`.

Coverage:
- GET /settings/providers returns a list of providers with `has_key`
  flags, never raw key material.
- PUT /settings/providers/{provider} stores an encrypted key (raw
  column on disk is Fernet ciphertext, decrypts back to plaintext).
- PUT /settings/model_overrides persists a role -> {provider, model}
  map under the `model_overrides` key in `settings_kv`.
- PUT /settings/search_provider validates the active search provider
  enum and persists under the `search_provider` key.
- PUT /settings/max_stage_retries validates the 1..5 range.
- GET /settings returns the consolidated snapshot (providers +
  overrides + search provider + max retries) with no raw keys.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import httpx
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import delete, text

from app.core.config import get_settings
from app.core.db import AsyncSessionLocal
from app.main import create_app
from app.models import SINGLETON_USER_ID, ProviderKey, SettingKV
from app.services.settings_service import SettingsService


@pytest.fixture(autouse=True)
def _fernet_key(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("FERNET_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def _cleanup() -> None:
    session = AsyncSessionLocal()
    try:
        await session.execute(delete(ProviderKey).where(ProviderKey.user_id == SINGLETON_USER_ID))
        await session.execute(delete(SettingKV).where(SettingKV.user_id == SINGLETON_USER_ID))
        await session.commit()
    finally:
        await session.close()


@pytest.fixture(autouse=True)
async def _clean_db() -> AsyncIterator[None]:
    await _cleanup()
    yield
    await _cleanup()


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_get_providers_returns_has_key_flags(client: httpx.AsyncClient) -> None:
    # Seed an anthropic key directly via the service.
    session = AsyncSessionLocal()
    try:
        await SettingsService(session).set_provider_key("anthropic", "sk-test-aaa")
    finally:
        await session.close()

    resp = await client.get("/settings/providers")
    assert resp.status_code == 200
    body = resp.json()
    assert "providers" in body
    by_name = {row["provider"]: row["has_key"] for row in body["providers"]}

    # Whole known list must be present.
    expected = {"anthropic", "openai", "google", "aws", "ollama", "tavily", "exa", "perplexity"}
    assert expected.issubset(by_name.keys())

    assert by_name["anthropic"] is True
    assert by_name["openai"] is False

    # Defensive: response must NOT contain any extraneous key field.
    for row in body["providers"]:
        assert set(row.keys()) == {"provider", "has_key"}


async def test_put_provider_key_stores_encrypted(client: httpx.AsyncClient) -> None:
    plaintext = "sk-test-12345"
    resp = await client.put("/settings/providers/anthropic", json={"key": plaintext})
    assert resp.status_code == 204
    assert resp.content == b""

    # Inspect the raw column — must be Fernet ciphertext, not plaintext.
    session = AsyncSessionLocal()
    try:
        result = await session.execute(
            text(
                "SELECT encrypted_key FROM provider_keys "
                "WHERE user_id = :uid AND provider = 'anthropic'"
            ),
            {"uid": SINGLETON_USER_ID},
        )
        raw = result.scalar_one()
        assert raw != plaintext
        assert raw.startswith("gAAAAA")

        # Round-trip: service decrypts back to plaintext.
        assert await SettingsService(session).get_provider_key("anthropic") == plaintext
    finally:
        await session.close()


async def test_put_provider_key_rejects_empty(client: httpx.AsyncClient) -> None:
    resp = await client.put("/settings/providers/anthropic", json={"key": ""})
    assert resp.status_code == 422


async def test_put_model_overrides_stores_map(client: httpx.AsyncClient) -> None:
    payload = {
        "overrides": {
            "framing": {"provider": "anthropic", "model": "claude-3-7-sonnet"},
            "research": {"provider": "openai", "model": "gpt-4o"},
        }
    }
    resp = await client.put("/settings/model_overrides", json=payload)
    assert resp.status_code == 204

    session = AsyncSessionLocal()
    try:
        stored = await SettingsService(session).get_setting("model_overrides")
    finally:
        await session.close()
    assert stored is not None
    assert stored["overrides"] == payload["overrides"]


async def test_put_search_provider_accepts_known(client: httpx.AsyncClient) -> None:
    resp = await client.put("/settings/search_provider", json={"provider": "tavily"})
    assert resp.status_code == 204

    session = AsyncSessionLocal()
    try:
        stored = await SettingsService(session).get_setting("search_provider")
    finally:
        await session.close()
    assert stored == {"provider": "tavily"}


async def test_put_search_provider_rejects_unknown(client: httpx.AsyncClient) -> None:
    resp = await client.put("/settings/search_provider", json={"provider": "bogus"})
    assert resp.status_code == 422


async def test_put_max_stage_retries_in_range(client: httpx.AsyncClient) -> None:
    resp = await client.put("/settings/max_stage_retries", json={"value": 3})
    assert resp.status_code == 204

    session = AsyncSessionLocal()
    try:
        stored = await SettingsService(session).get_setting("max_stage_retries")
    finally:
        await session.close()
    assert stored == {"value": 3}


@pytest.mark.parametrize("bad", [0, -1, 6, 100])
async def test_put_max_stage_retries_rejects_out_of_range(
    client: httpx.AsyncClient, bad: int
) -> None:
    resp = await client.put("/settings/max_stage_retries", json={"value": bad})
    assert resp.status_code == 422


async def test_get_settings_snapshot_combines_state(client: httpx.AsyncClient) -> None:
    # Populate everything via the API.
    assert (
        await client.put("/settings/providers/anthropic", json={"key": "sk-aaa"})
    ).status_code == 204
    assert (
        await client.put(
            "/settings/model_overrides",
            json={"overrides": {"framing": {"provider": "anthropic", "model": "claude-x"}}},
        )
    ).status_code == 204
    assert (
        await client.put("/settings/search_provider", json={"provider": "exa"})
    ).status_code == 204
    assert (await client.put("/settings/max_stage_retries", json={"value": 4})).status_code == 204

    resp = await client.get("/settings")
    assert resp.status_code == 200
    body = resp.json()

    by_name = {row["provider"]: row["has_key"] for row in body["providers"]}
    assert by_name["anthropic"] is True
    assert by_name["openai"] is False

    assert body["model_overrides"] == {"framing": {"provider": "anthropic", "model": "claude-x"}}
    assert body["search_provider"] == "exa"
    assert body["max_stage_retries"] == 4


async def test_get_settings_snapshot_uses_defaults_when_unset(client: httpx.AsyncClient) -> None:
    resp = await client.get("/settings")
    assert resp.status_code == 200
    body = resp.json()
    assert body["model_overrides"] == {}
    assert body["search_provider"] is None
    assert body["max_stage_retries"] == 2


async def test_get_providers_never_exposes_raw_key(client: httpx.AsyncClient) -> None:
    plaintext = "sk-do-not-leak-9c3a7e1b"
    assert (
        await client.put("/settings/providers/anthropic", json={"key": plaintext})
    ).status_code == 204

    # Scan both endpoints for the literal plaintext substring.
    providers_body = (await client.get("/settings/providers")).text
    snapshot_body = (await client.get("/settings")).text

    assert plaintext not in providers_body
    assert plaintext not in snapshot_body

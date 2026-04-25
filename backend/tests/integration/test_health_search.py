"""Integration tests for GET /health/search (M4.7)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import httpx
import pytest
import respx
from cryptography.fernet import Fernet
from httpx import Response
from sqlalchemy import delete

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
    async with AsyncSessionLocal() as session:
        await session.execute(delete(ProviderKey).where(ProviderKey.user_id == SINGLETON_USER_ID))
        await session.execute(delete(SettingKV).where(SettingKV.user_id == SINGLETON_USER_ID))
        await session.commit()


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


@pytest.mark.asyncio
@respx.mock
async def test_health_search_returns_top_titles(client: httpx.AsyncClient) -> None:
    async with AsyncSessionLocal() as session:
        svc = SettingsService(session)
        await svc.set_provider_key("tavily", "tvly-test-key")
        await svc.set_setting("search_provider", {"provider": "tavily"})

    route = respx.post("https://api.tavily.com/search").mock(
        return_value=Response(
            200,
            json={
                "results": [
                    {"title": "One", "url": "https://example.com/1", "content": "a"},
                    {"title": "Two", "url": "https://example.com/2", "content": "b"},
                    {"title": "Three", "url": "https://example.com/3", "content": "c"},
                    {"title": "Four", "url": "https://example.com/4", "content": "d"},
                ]
            },
        )
    )

    resp = await client.get("/health/search", params={"q": "test"})
    assert resp.status_code == 200, resp.text
    assert route.called
    assert resp.json() == {"titles": ["One", "Two", "Three"]}


@pytest.mark.asyncio
async def test_health_search_400_when_provider_key_missing(client: httpx.AsyncClient) -> None:
    async with AsyncSessionLocal() as session:
        await SettingsService(session).set_setting("search_provider", {"provider": "tavily"})

    resp = await client.get("/health/search", params={"q": "test"})
    assert resp.status_code == 400
    assert "No API key configured" in resp.json()["detail"]

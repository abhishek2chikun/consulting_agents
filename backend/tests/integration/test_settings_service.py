"""Integration tests for `SettingsService.set/get_provider_key`.

Hits real Postgres (`make db-up` + `alembic upgrade head` required) and
verifies that:

1. `set_provider_key` stores ciphertext at rest (raw column never holds
   the plaintext key — checked via direct `SELECT encrypted_key`).
2. `get_provider_key` round-trips through `crypto.unwrap` to plaintext,
   and returns `None` for missing rows.
3. Setting the same `(user_id, provider)` twice replaces the existing
   row in place (upsert), not appending a second row.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import delete, func, select, text

from app.core.config import get_settings
from app.core.db import AsyncSessionLocal
from app.models import SINGLETON_USER_ID, ProviderKey
from app.services.settings_service import SettingsService


@pytest.fixture(autouse=True)
def _fernet_key(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Provision a fresh Fernet key for each test and reset Settings cache."""
    monkeypatch.setenv("FERNET_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def _cleanup() -> None:
    session = AsyncSessionLocal()
    try:
        await session.execute(delete(ProviderKey).where(ProviderKey.user_id == SINGLETON_USER_ID))
        await session.commit()
    finally:
        await session.close()


@pytest.fixture(autouse=True)
async def _clean_provider_keys() -> None:
    await _cleanup()
    yield
    await _cleanup()


async def test_set_provider_key_stores_encrypted() -> None:
    session = AsyncSessionLocal()
    try:
        service = SettingsService(session)
        await service.set_provider_key("anthropic", "sk-test-12345")

        # Read the raw column back via SQL — bypass any ORM-level decoding.
        result = await session.execute(
            text(
                "SELECT encrypted_key FROM provider_keys "
                "WHERE user_id = :uid AND provider = 'anthropic'"
            ),
            {"uid": SINGLETON_USER_ID},
        )
        raw = result.scalar_one()

        assert raw != "sk-test-12345", "raw column must not contain plaintext"
        # Fernet tokens are base64-url-safe and start with the version byte
        # 0x80 -> base64 prefix "gAAAAA".
        assert raw.startswith("gAAAAA"), f"expected Fernet token, got: {raw!r}"
    finally:
        await session.close()


async def test_get_provider_key_returns_plaintext() -> None:
    session = AsyncSessionLocal()
    try:
        service = SettingsService(session)
        await service.set_provider_key("anthropic", "sk-test-12345")

        assert await service.get_provider_key("anthropic") == "sk-test-12345"
        assert await service.get_provider_key("openai") is None
    finally:
        await session.close()


async def test_overwrite_provider_key_replaces_value() -> None:
    session = AsyncSessionLocal()
    try:
        service = SettingsService(session)
        await service.set_provider_key("anthropic", "old-key")
        await service.set_provider_key("anthropic", "new-key")

        assert await service.get_provider_key("anthropic") == "new-key"

        count = await session.execute(
            select(func.count())
            .select_from(ProviderKey)
            .where(
                ProviderKey.user_id == SINGLETON_USER_ID,
                ProviderKey.provider == "anthropic",
            )
        )
        assert count.scalar_one() == 1, "upsert must not create a second row"
    finally:
        await session.close()

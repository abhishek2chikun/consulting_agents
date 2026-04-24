"""SettingsService — encrypted provider-key storage + JSON KV settings.

V1 is single-user: every method targets `SINGLETON_USER_ID` implicitly.
The service does not accept a `user_id` parameter on purpose — when
multi-user lands, the signatures will change deliberately rather than
silently routing through whatever `user_id` callers happen to pass.

Plaintext API keys flow through this service exactly twice per write
(`set_provider_key`) and once per read (`get_provider_key`); the
`provider_keys` table only ever contains Fernet ciphertext (see
`app.core.crypto`).

Generic settings (model overrides, active search provider, max retries,
etc.) live in `settings_kv` as JSONB blobs keyed by string. Per-key
schema validation is the route handler's responsibility (Pydantic at the
API boundary in `app.api.settings`); this layer just shuttles dicts.

All write methods commit before returning. This matches the V1
single-method-per-request call pattern used by route handlers; if a
future caller needs to bundle writes into a larger transaction, those
methods grow an explicit `commit: bool = True` flag rather than
silently changing semantics.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import crypto
from app.models import SINGLETON_USER_ID, ProviderKey, SettingKV

# Closed set of providers known to the V1 system. Includes both LLM
# providers and search providers because both store API keys via the
# same `provider_keys` table — the active search provider selection
# lives separately in `settings_kv['search_provider']`.
KNOWN_PROVIDERS: tuple[str, ...] = (
    "anthropic",
    "openai",
    "google",
    "aws",
    "ollama",
    "tavily",
    "exa",
    "perplexity",
)

# Default for `max_stage_retries` when no explicit value has been
# persisted yet. Mirrors the agent runtime default in M5.
DEFAULT_MAX_STAGE_RETRIES = 2


class SettingsService:
    """Per-user settings reads/writes (provider keys + JSON KV)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Provider keys (encrypted-at-rest)
    # ------------------------------------------------------------------

    async def set_provider_key(self, provider: str, key: str) -> None:
        """Encrypt `key` and upsert it for `(SINGLETON_USER_ID, provider)`.

        `provider` is normalized to lowercase + stripped. Both arguments
        must be non-empty after normalization; otherwise `ValueError`.
        """
        normalized = provider.strip().lower()
        if not normalized:
            raise ValueError("provider must be a non-empty string")
        if not key:
            raise ValueError("key must be a non-empty string")

        encrypted = crypto.wrap(key)

        stmt = insert(ProviderKey).values(
            user_id=SINGLETON_USER_ID,
            provider=normalized,
            encrypted_key=encrypted,
        )
        # ON CONFLICT on the unique (user_id, provider) constraint — replace
        # ciphertext in place and bump updated_at. We do NOT touch id /
        # created_at on update.
        stmt = stmt.on_conflict_do_update(
            index_elements=[ProviderKey.user_id, ProviderKey.provider],
            set_={
                "encrypted_key": stmt.excluded.encrypted_key,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        await self._session.execute(stmt)
        await self._session.commit()

    async def get_provider_key(self, provider: str) -> str | None:
        """Return the decrypted key for `provider`, or `None` if unset."""
        normalized = provider.strip().lower()
        if not normalized:
            raise ValueError("provider must be a non-empty string")

        result = await self._session.execute(
            select(ProviderKey.encrypted_key).where(
                ProviderKey.user_id == SINGLETON_USER_ID,
                ProviderKey.provider == normalized,
            )
        )
        ciphertext = result.scalar_one_or_none()
        if ciphertext is None:
            return None
        return crypto.unwrap(ciphertext)

    async def list_provider_keys(self) -> list[str]:
        """Return the (sorted) provider names that currently have a key."""
        result = await self._session.execute(
            select(ProviderKey.provider).where(ProviderKey.user_id == SINGLETON_USER_ID)
        )
        return sorted(result.scalars().all())

    # ------------------------------------------------------------------
    # Generic JSON KV (settings_kv)
    # ------------------------------------------------------------------

    async def get_setting(self, key: str) -> dict[str, Any] | None:
        """Return the JSON value stored under `key`, or `None`."""
        normalized = key.strip()
        if not normalized:
            raise ValueError("key must be a non-empty string")

        result = await self._session.execute(
            select(SettingKV.value).where(
                SettingKV.user_id == SINGLETON_USER_ID,
                SettingKV.key == normalized,
            )
        )
        return result.scalar_one_or_none()

    async def set_setting(self, key: str, value: dict[str, Any]) -> None:
        """Upsert `value` under `(SINGLETON_USER_ID, key)`."""
        normalized = key.strip()
        if not normalized:
            raise ValueError("key must be a non-empty string")

        stmt = insert(SettingKV).values(
            user_id=SINGLETON_USER_ID,
            key=normalized,
            value=value,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[SettingKV.user_id, SettingKV.key],
            set_={"value": stmt.excluded.value},
        )
        await self._session.execute(stmt)
        await self._session.commit()

    # ------------------------------------------------------------------
    # Snapshot (convenience for the frontend bootstrap GET /settings)
    # ------------------------------------------------------------------

    async def get_settings_snapshot(self) -> dict[str, Any]:
        """Assemble the full settings snapshot.

        Shape:
            {
              "providers": [{"provider": str, "has_key": bool}, ...],
              "model_overrides": {role: {"provider": str, "model": str}, ...},
              "search_provider": str | None,
              "max_stage_retries": int,
            }

        Defaults are applied here (not at the DB layer) so unconfigured
        installs return a sensible bootstrap payload.
        """
        present = set(await self.list_provider_keys())
        providers = [{"provider": name, "has_key": name in present} for name in KNOWN_PROVIDERS]

        overrides_row = await self.get_setting("model_overrides")
        model_overrides = (
            overrides_row.get("overrides", {}) if isinstance(overrides_row, dict) else {}
        )

        search_row = await self.get_setting("search_provider")
        search_provider = search_row.get("provider") if isinstance(search_row, dict) else None

        retries_row = await self.get_setting("max_stage_retries")
        max_stage_retries = (
            retries_row.get("value", DEFAULT_MAX_STAGE_RETRIES)
            if isinstance(retries_row, dict)
            else DEFAULT_MAX_STAGE_RETRIES
        )

        return {
            "providers": providers,
            "model_overrides": model_overrides,
            "search_provider": search_provider,
            "max_stage_retries": max_stage_retries,
        }


__all__ = ["DEFAULT_MAX_STAGE_RETRIES", "KNOWN_PROVIDERS", "SettingsService"]

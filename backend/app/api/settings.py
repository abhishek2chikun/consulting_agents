"""Settings REST API (M2.4).

Mounts at `/settings`. Backed by `SettingsService`; all writes return
`204 No Content` on success and rely on Pydantic for `422` validation.

Security note: GET endpoints expose only `has_key: bool` flags — raw
provider keys never leave the server. The defensive
`test_get_providers_never_exposes_raw_key` test pins this guarantee.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.schemas.settings import (
    MaxStageRetriesRequest,
    ModelOverridesRequest,
    ProviderInfo,
    ProvidersResponse,
    SearchProviderRequest,
    SetProviderKeyRequest,
    SettingsSnapshot,
)
from app.services.settings_service import KNOWN_PROVIDERS, SettingsService

router = APIRouter(prefix="/settings", tags=["settings"])


# Annotated-based dependency wiring keeps `Depends(...)` out of default-arg
# position (ruff B008) while preserving FastAPI's signature-driven DI.
SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_settings_service(session: SessionDep) -> SettingsService:
    """FastAPI dependency factory: per-request `SettingsService`."""
    return SettingsService(session)


SettingsServiceDep = Annotated[SettingsService, Depends(get_settings_service)]


@router.get("/providers", response_model=ProvidersResponse)
async def list_providers(svc: SettingsServiceDep) -> ProvidersResponse:
    present = set(await svc.list_provider_keys())
    return ProvidersResponse(
        providers=[ProviderInfo(provider=name, has_key=name in present) for name in KNOWN_PROVIDERS]
    )


@router.put("/providers/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def set_provider_key(
    provider: str,
    body: SetProviderKeyRequest,
    svc: SettingsServiceDep,
) -> None:
    await svc.set_provider_key(provider, body.key)


@router.put("/model_overrides", status_code=status.HTTP_204_NO_CONTENT)
async def set_model_overrides(
    body: ModelOverridesRequest,
    svc: SettingsServiceDep,
) -> None:
    await svc.set_setting("model_overrides", body.model_dump())


@router.put("/search_provider", status_code=status.HTTP_204_NO_CONTENT)
async def set_search_provider(
    body: SearchProviderRequest,
    svc: SettingsServiceDep,
) -> None:
    await svc.set_setting("search_provider", body.model_dump())


@router.put("/max_stage_retries", status_code=status.HTTP_204_NO_CONTENT)
async def set_max_stage_retries(
    body: MaxStageRetriesRequest,
    svc: SettingsServiceDep,
) -> None:
    await svc.set_setting("max_stage_retries", body.model_dump())


@router.get("", response_model=SettingsSnapshot)
async def get_settings_snapshot(svc: SettingsServiceDep) -> SettingsSnapshot:
    snapshot = await svc.get_settings_snapshot()
    return SettingsSnapshot.model_validate(snapshot)


__all__ = ["router"]

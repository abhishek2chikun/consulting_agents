"""Health and diagnostics API routes (M4.7)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.tools.providers.base import SearchProvider
from app.agents.tools.providers.duckduckgo import DuckDuckGoProvider
from app.agents.tools.providers.exa import ExaProvider
from app.agents.tools.providers.perplexity import PerplexityProvider
from app.agents.tools.providers.tavily import TavilyProvider
from app.core.db import get_session
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/health", tags=["health"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _provider_instance(name: str, api_key: str | None) -> SearchProvider:
    if name == "duckduckgo":
        return DuckDuckGoProvider()
    key = api_key or ""
    if name == "tavily":
        return TavilyProvider(api_key=key)
    if name == "exa":
        return ExaProvider(api_key=key)
    if name == "perplexity":
        return PerplexityProvider(api_key=key)
    raise ValueError(f"Unsupported search provider: {name}")


@router.get("/search")
async def health_search(
    q: Annotated[str, Query(min_length=1)],
    session: SessionDep,
) -> dict[str, list[str]]:
    svc = SettingsService(session)

    row = await svc.get_setting("search_provider")
    provider = row.get("provider") if isinstance(row, dict) else "duckduckgo"
    if not isinstance(provider, str):
        provider = "duckduckgo"

    # DuckDuckGo needs no key — skip the key lookup for it.
    key: str | None = None
    if provider != "duckduckgo":
        key = await svc.get_provider_key(provider)
        if not key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No API key configured for provider '{provider}'",
            )

    try:
        adapter = _provider_instance(provider, key)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    results = await adapter.search(q, k=3)
    return {"titles": [r.title for r in results[:3]]}


__all__ = ["router"]

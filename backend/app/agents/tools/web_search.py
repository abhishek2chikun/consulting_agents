"""Provider-agnostic web_search tool with evidence registration."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any, TypedDict

from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.tools.cite import register_evidence
from app.agents.tools.providers.base import SearchProvider
from app.agents.tools.providers.exa import ExaProvider
from app.agents.tools.providers.perplexity import PerplexityProvider
from app.agents.tools.providers.tavily import TavilyProvider
from app.models.evidence import EvidenceKind
from app.services.settings_service import SettingsService


class WebSearchHit(TypedDict):
    src_id: str
    title: str
    snippet: str
    url: str


def _provider_adapter(name: str, api_key: str) -> SearchProvider:
    if name == "tavily":
        return TavilyProvider(api_key=api_key)
    if name == "exa":
        return ExaProvider(api_key=api_key)
    if name == "perplexity":
        return PerplexityProvider(api_key=api_key)
    raise ValueError(f"Unsupported search provider: {name}")


def build_web_search(
    run_id: uuid.UUID,
    session_factory: Callable[[], AsyncSession],
) -> Any:
    @tool
    async def web_search(query: str, k: int = 5) -> list[dict[str, Any]]:
        """Run provider-backed web search and register each hit as Evidence."""
        if not query or not query.strip() or k <= 0:
            return []

        async with session_factory() as session:
            svc = SettingsService(session)
            row = await svc.get_setting("search_provider")
            provider = row.get("provider") if isinstance(row, dict) else "tavily"
            if not isinstance(provider, str):
                provider = "tavily"

            key = await svc.get_provider_key(provider)
            if key is None:
                raise ValueError(f"No API key configured for provider '{provider}'")

            adapter = _provider_adapter(provider, key)
            results = await adapter.search(query, k)

            out: list[WebSearchHit] = []
            for item in results:
                src_id = await register_evidence(
                    session,
                    run_id,
                    kind=EvidenceKind.web,
                    url=str(item.url),
                    chunk_id=None,
                    title=item.title,
                    snippet=item.snippet,
                    provider=provider,
                )
                out.append(
                    WebSearchHit(
                        src_id=src_id,
                        title=item.title,
                        snippet=item.snippet,
                        url=str(item.url),
                    )
                )

            return [dict(hit) for hit in out]

    return web_search


__all__ = ["build_web_search"]

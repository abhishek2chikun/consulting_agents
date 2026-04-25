"""Tavily search-provider adapter (M4.2)."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from app.agents.tools.providers.base import SearchResult


class TavilyProvider:
    """Adapter for Tavily's `/search` endpoint."""

    BASE_URL = "https://api.tavily.com/search"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def search(self, query: str, k: int) -> list[SearchResult]:
        if not query.strip() or k <= 0:
            return []

        payload = {
            "api_key": self._api_key,
            "query": query,
            "max_results": k,
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(self.BASE_URL, json=payload)
            response.raise_for_status()
            body = response.json()

        out: list[SearchResult] = []
        for item in body.get("results", [])[:k]:
            published = _parse_iso_datetime(item.get("published_date"))
            out.append(
                SearchResult(
                    title=str(item.get("title", "")),
                    url=str(item.get("url", "")),
                    snippet=str(item.get("content", "")),
                    published_at=published,
                    source="tavily",
                )
            )
        return out


def _parse_iso_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or value.strip() == "":
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


__all__ = ["TavilyProvider"]

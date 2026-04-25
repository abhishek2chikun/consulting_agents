"""Search-provider protocol and normalized result schema (M4.1)."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from pydantic import BaseModel


class SearchResult(BaseModel):
    """Provider-agnostic web search result."""

    title: str
    url: str
    snippet: str
    published_at: datetime | None = None
    source: str


class SearchProvider(Protocol):
    """Minimal adapter contract for all web-search backends."""

    async def search(self, query: str, k: int) -> list[SearchResult]:
        """Return up to `k` normalized results for `query`."""


__all__ = ["SearchProvider", "SearchResult"]

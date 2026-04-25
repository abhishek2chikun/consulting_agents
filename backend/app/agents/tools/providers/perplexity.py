"""Perplexity search-provider adapter (M4.4)."""

from __future__ import annotations

from urllib.parse import urlparse

import httpx

from app.agents.tools.providers.base import SearchResult


class PerplexityProvider:
    """Adapter over Perplexity's `chat/completions` endpoint."""

    BASE_URL = "https://api.perplexity.ai/chat/completions"

    def __init__(self, api_key: str, model: str = "pplx-online") -> None:
        self._api_key = api_key
        self._model = model

    async def search(self, query: str, k: int) -> list[SearchResult]:
        if not query.strip() or k <= 0:
            return []

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": "Return citations for the user query.",
                },
                {"role": "user", "content": query},
            ],
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(self.BASE_URL, headers=headers, json=payload)
            response.raise_for_status()
            body = response.json()

        citations = _extract_citations(body)[:k]
        out: list[SearchResult] = []
        for url in citations:
            hostname = urlparse(url).hostname or "source"
            out.append(
                SearchResult(
                    title=hostname,
                    url=url,
                    snippet=f"Cited by Perplexity for query: {query}",
                    published_at=None,
                    source="perplexity",
                )
            )
        return out


def _extract_citations(body: dict[str, object]) -> list[str]:
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        return []
    first = choices[0]
    if not isinstance(first, dict):
        return []
    message = first.get("message")
    if not isinstance(message, dict):
        return []
    citations = message.get("citations")
    if not isinstance(citations, list):
        return []
    return [str(c) for c in citations if isinstance(c, str)]


__all__ = ["PerplexityProvider"]

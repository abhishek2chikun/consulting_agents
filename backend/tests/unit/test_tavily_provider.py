"""Unit tests for Tavily search provider adapter (M4.2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import respx
from httpx import Response

from app.agents.tools.providers.tavily import TavilyProvider

FIXTURE = Path(__file__).parent.parent / "fixtures" / "tavily_response.json"


@pytest.mark.asyncio
@respx.mock
async def test_tavily_provider_normalizes_results() -> None:
    payload = json.loads(FIXTURE.read_text())

    route = respx.post("https://api.tavily.com/search").mock(
        return_value=Response(200, json=payload)
    )

    provider = TavilyProvider(api_key="tvly-test-key")
    results = await provider.search("market entry strategy", k=3)

    assert route.called
    assert len(results) == 3

    first = results[0]
    assert first.title == "Market Entry Strategy Guide"
    assert str(first.url) == "https://example.com/market-entry-guide"
    assert first.source == "tavily"
    assert first.published_at is not None

    second = results[1]
    assert second.published_at is None

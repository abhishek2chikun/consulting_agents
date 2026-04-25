"""Unit tests for Perplexity search provider adapter (M4.4)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import respx
from httpx import Response

from app.agents.tools.providers.perplexity import PerplexityProvider

FIXTURE = Path(__file__).parent.parent / "fixtures" / "perplexity_response.json"


@pytest.mark.asyncio
@respx.mock
async def test_perplexity_provider_maps_citations_to_results() -> None:
    payload = json.loads(FIXTURE.read_text())

    route = respx.post("https://api.perplexity.ai/chat/completions").mock(
        return_value=Response(200, json=payload)
    )

    provider = PerplexityProvider(api_key="pplx-test-key")
    results = await provider.search("market entry", k=3)

    assert route.called
    assert len(results) == 3
    assert results[0].source == "perplexity"
    assert str(results[0].url) == "https://example.com/market-overview"
    assert results[0].title == "example.com"
    assert "Cited by Perplexity" in results[0].snippet

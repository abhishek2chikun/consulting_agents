"""Unit tests for Exa search provider adapter (M4.3)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import respx
from httpx import Response

from app.agents.tools.providers.exa import ExaProvider

FIXTURE = Path(__file__).parent.parent / "fixtures" / "exa_response.json"


@pytest.mark.asyncio
@respx.mock
async def test_exa_provider_normalizes_results() -> None:
    payload = json.loads(FIXTURE.read_text())

    route = respx.post("https://api.exa.ai/search").mock(return_value=Response(200, json=payload))

    provider = ExaProvider(api_key="exa-test-key")
    results = await provider.search("tam framework", k=3)

    assert route.called
    assert len(results) == 3

    first = results[0]
    assert first.title == "Global TAM Estimation Framework"
    assert str(first.url) == "https://example.com/tam-framework"
    assert first.source == "exa"
    assert first.published_at is not None

    second = results[1]
    assert second.published_at is None

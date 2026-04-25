"""Unit tests for search-provider base types (M4.1)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.agents.tools.providers.base import SearchResult


def test_search_result_round_trip_serialization() -> None:
    now = datetime.now(tz=UTC).replace(microsecond=0)
    original = SearchResult(
        title="Launch report",
        url="https://example.com/report",
        snippet="Key findings for market entry.",
        published_at=now,
        source="tavily",
    )

    dumped = original.model_dump(mode="json")
    rebuilt = SearchResult.model_validate(dumped)

    assert rebuilt == original

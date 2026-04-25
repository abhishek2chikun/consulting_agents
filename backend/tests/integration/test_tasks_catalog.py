"""Integration tests for the tasks catalog API (M3.1).

Pins the seeded contents of `task_types`: V1 ships `market_entry`
(enabled) and `ma` (disabled stub for V2). The endpoint returns a bare
list ordered by slug; the frontend renders it as the task picker on the
"new run" page.
"""

from __future__ import annotations

import httpx
import pytest

from app.main import app


@pytest.mark.asyncio
async def test_get_tasks_returns_seeded_catalog() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/tasks")

    assert res.status_code == 200
    body = res.json()
    assert isinstance(body, list)

    by_slug = {t["slug"]: t for t in body}
    assert "market_entry" in by_slug
    assert "ma" in by_slug
    assert by_slug["market_entry"]["name"] == "Market Entry"
    assert by_slug["market_entry"]["enabled"] is True
    assert by_slug["ma"]["name"] == "M&A"
    assert by_slug["ma"]["enabled"] is True


@pytest.mark.asyncio
async def test_get_tasks_is_sorted_by_slug() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/tasks")

    assert res.status_code == 200
    slugs = [t["slug"] for t in res.json()]
    assert slugs == sorted(slugs)

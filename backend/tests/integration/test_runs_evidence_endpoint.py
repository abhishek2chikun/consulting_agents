"""Integration tests for `GET /runs/{id}/evidence` (M7.4)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import httpx
import pytest

from app.core.db import AsyncSessionLocal
from app.main import create_app
from app.models import (
    SINGLETON_USER_ID,
    Evidence,
    EvidenceKind,
    Run,
    RunStatus,
)


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _seed_run_with_evidence(rows: list[dict[str, object]]) -> uuid.UUID:
    async with AsyncSessionLocal() as session:
        run = Run(
            user_id=SINGLETON_USER_ID,
            task_id="market_entry",
            goal="evidence-listing test",
            status=RunStatus.completed,
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)

        for row in rows:
            session.add(
                Evidence(
                    run_id=run.id,
                    src_id=str(row["src_id"]),
                    kind=EvidenceKind(row["kind"]),
                    url=row.get("url"),  # type: ignore[arg-type]
                    title=str(row["title"]),
                    snippet=str(row["snippet"]),
                    provider=str(row["provider"]),
                )
            )
        await session.commit()
        return run.id


@pytest.mark.asyncio
async def test_get_evidence_returns_all_rows_for_run(
    client: httpx.AsyncClient,
) -> None:
    run_id = await _seed_run_with_evidence(
        [
            {
                "src_id": "s1",
                "kind": "web",
                "url": "https://example.com/a",
                "title": "Source A",
                "snippet": "snippet A",
                "provider": "tavily",
            },
            {
                "src_id": "s2",
                "kind": "doc",
                "url": None,
                "title": "Source B",
                "snippet": "snippet B",
                "provider": "rag",
            },
        ]
    )

    res = await client.get(f"/runs/{run_id}/evidence")
    assert res.status_code == 200
    body = res.json()
    assert "evidence" in body
    items = body["evidence"]
    assert len(items) == 2
    by_src = {item["src_id"]: item for item in items}
    assert by_src["s1"]["url"] == "https://example.com/a"
    assert by_src["s1"]["title"] == "Source A"
    assert by_src["s1"]["kind"] == "web"
    assert by_src["s1"]["provider"] == "tavily"
    assert by_src["s2"]["url"] is None
    assert by_src["s2"]["kind"] == "doc"


@pytest.mark.asyncio
async def test_get_evidence_returns_empty_list_when_no_rows(
    client: httpx.AsyncClient,
) -> None:
    run_id = await _seed_run_with_evidence([])
    res = await client.get(f"/runs/{run_id}/evidence")
    assert res.status_code == 200
    assert res.json() == {"evidence": []}


@pytest.mark.asyncio
async def test_get_evidence_404_for_unknown_run(
    client: httpx.AsyncClient,
) -> None:
    res = await client.get(f"/runs/{uuid.uuid4()}/evidence")
    assert res.status_code == 404

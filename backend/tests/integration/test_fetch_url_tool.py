"""Integration test for fetch_url tool with evidence registration (M4.6)."""

from __future__ import annotations

import uuid

import pytest
import respx
from httpx import Response
from sqlalchemy import delete, select

from app.agents.tools.fetch_url import build_fetch_url
from app.core.db import AsyncSessionLocal
from app.models import SINGLETON_USER_ID, Evidence, Run, RunStatus


@pytest.mark.asyncio
@respx.mock
async def test_fetch_url_returns_snippet_and_writes_evidence() -> None:
    run_id = uuid.uuid4()
    url = "https://example.com/article"

    async with AsyncSessionLocal() as session:
        session.add(
            Run(
                id=run_id,
                user_id=SINGLETON_USER_ID,
                task_id="market_entry",
                goal="fetch tool test",
                status=RunStatus.running,
                model_snapshot={},
            )
        )
        await session.commit()

    html = """
    <html><head><title>Example Article</title></head>
    <body><main><p>Paragraph one.</p><p>Paragraph two about market entry.</p></main></body></html>
    """
    route = respx.get(url).mock(return_value=Response(200, text=html))

    tool = build_fetch_url(run_id, AsyncSessionLocal)
    result = await tool.ainvoke({"url": url})

    assert route.called
    assert set(result.keys()) == {"src_id", "title", "snippet", "url"}
    assert result["url"] == url
    assert "market entry" in result["snippet"].lower()

    async with AsyncSessionLocal() as session:
        rows = (await session.execute(select(Evidence).where(Evidence.run_id == run_id))).scalars()
        evidence = list(rows)
        assert len(evidence) == 1
        assert evidence[0].url == url

    async with AsyncSessionLocal() as session:
        await session.execute(delete(Run).where(Run.id == run_id))
        await session.commit()

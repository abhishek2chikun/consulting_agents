"""Integration test for provider-agnostic web_search tool (M4.5)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
import respx
from httpx import Response
from sqlalchemy import delete, select

from app.agents.tools.web_search import build_web_search
from app.core.db import AsyncSessionLocal
from app.models import SINGLETON_USER_ID, Evidence, Run, RunStatus
from app.services.settings_service import SettingsService

FIXTURE = Path(__file__).parent.parent / "fixtures" / "tavily_response.json"


@pytest.mark.asyncio
@respx.mock
async def test_web_search_returns_hits_and_writes_evidence() -> None:
    run_id = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        session.add(
            Run(
                id=run_id,
                user_id=SINGLETON_USER_ID,
                task_id="market_entry",
                goal="web search test",
                status=RunStatus.running,
                model_snapshot={},
            )
        )
        svc = SettingsService(session)
        await svc.set_setting("search_provider", {"provider": "tavily"})
        await svc.set_provider_key("tavily", "tvly-test-key")
        await session.commit()

    payload = json.loads(FIXTURE.read_text())
    route = respx.post("https://api.tavily.com/search").mock(
        return_value=Response(200, json=payload)
    )

    tool = build_web_search(run_id, AsyncSessionLocal)
    hits = await tool.ainvoke({"query": "market entry", "k": 3})

    assert route.called
    assert len(hits) == 3
    assert set(hits[0].keys()) == {"src_id", "title", "snippet", "url"}

    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(Evidence).where(Evidence.run_id == run_id).order_by(Evidence.src_id)
            )
        ).scalars()
        evidence = list(rows)
        assert len(evidence) == 3

    async with AsyncSessionLocal() as session:
        await session.execute(delete(Run).where(Run.id == run_id))
        await session.commit()

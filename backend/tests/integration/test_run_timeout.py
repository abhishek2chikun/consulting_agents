"""Integration test for per-run timeout enforcement in the worker."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import select

from app.agents.market_entry.profile import MARKET_ENTRY_PROFILE
from app.core.config import get_settings
from app.core.db import AsyncSessionLocal
from app.models import SINGLETON_USER_ID, Artifact, Event, Run, RunStatus
from app.workers.run_worker import continue_after_framing


@pytest.mark.asyncio
async def test_continue_after_framing_fails_when_timeout_budget_is_exceeded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RUN_TIMEOUT_SECONDS", "2")
    monkeypatch.setenv("HEARTBEAT_INTERVAL_SECONDS", "1")
    get_settings.cache_clear()

    async with AsyncSessionLocal() as session:
        run = Run(
            user_id=SINGLETON_USER_ID,
            task_id="market_entry",
            goal="Enter EU EV-charging market",
            status=RunStatus.questioning,
        )
        session.add(run)
        await session.flush()
        run_id = run.id
        session.add(
            Artifact(
                run_id=run_id,
                path="framing/questionnaire.json",
                kind="json",
                content='{"items": []}',
            )
        )
        await session.commit()

    class BlockingStructuredModel:
        def with_structured_output(self, _schema: object) -> BlockingStructuredModel:
            return self

        async def ainvoke(self, _messages: object) -> object:
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

    def factory(_role: str) -> object:
        return BlockingStructuredModel()

    try:
        await asyncio.wait_for(
            continue_after_framing(
                run_id,
                answers={"time_horizon": "12 months"},
                profile=MARKET_ENTRY_PROFILE,
                model_factory=factory,
            ),
            timeout=5.0,
        )

        async with AsyncSessionLocal() as session:
            run = await session.get(Run, run_id)
            assert run is not None
            timeout_events = (
                (
                    await session.execute(
                        select(Event).where(
                            Event.run_id == run_id,
                            Event.type == "run_failed",
                        )
                    )
                )
                .scalars()
                .all()
            )

        assert run.status == RunStatus.failed
        assert run.started_at is not None
        assert run.completed_at is not None
        assert run.completed_at >= run.started_at
        assert len(timeout_events) == 1
        assert timeout_events[0].payload == {"reason": "timeout: exceeded 2 s budget"}
    finally:
        get_settings.cache_clear()

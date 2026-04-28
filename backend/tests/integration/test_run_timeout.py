"""Integration test for per-run timeout enforcement in the worker."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import select

from app.agents.market_entry.profile import MARKET_ENTRY_PROFILE
from app.core.config import get_settings
from app.core.db import AsyncSessionLocal
from app.models import SINGLETON_USER_ID, Artifact, Event, Run, RunStatus
from app.workers import run_worker
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

    def forbidden_timeout(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("timeout must be enforced by the heartbeat monitor")

    monkeypatch.setattr(run_worker.asyncio, "timeout", forbidden_timeout)

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


@pytest.mark.asyncio
async def test_continue_after_framing_prefers_explicit_cancel_over_timeout(
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

    async def flip_to_cancelling() -> None:
        await asyncio.sleep(0.5)
        async with AsyncSessionLocal() as session:
            run = await session.get(Run, run_id)
            assert run is not None
            run.status = RunStatus.cancelling
            await session.commit()

    flipper = asyncio.create_task(flip_to_cancelling())
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
        await flipper

        async with AsyncSessionLocal() as session:
            run = await session.get(Run, run_id)
            assert run is not None
            cancelled_events = (
                (
                    await session.execute(
                        select(Event).where(
                            Event.run_id == run_id,
                            Event.type == "run_cancelled",
                        )
                    )
                )
                .scalars()
                .all()
            )
            failed_events = (
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

        assert run.status == RunStatus.cancelled
        assert run.completed_at is not None
        assert len(cancelled_events) == 1
        assert failed_events == []
    finally:
        if not flipper.done():
            flipper.cancel()
            try:
                await flipper
            except asyncio.CancelledError:
                pass
        get_settings.cache_clear()

"""Integration test for per-run timeout enforcement in the worker."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.market_entry.profile import MARKET_ENTRY_PROFILE
from app.core.config import get_settings
from app.core.db import AsyncSessionLocal
from app.models import SINGLETON_USER_ID, Artifact, Event, Message, Run, RunStatus
from app.workers import run_worker
from app.workers.run_worker import continue_after_framing


async def _create_run(*, status: RunStatus = RunStatus.questioning) -> Run:
    async with AsyncSessionLocal() as session:
        run = Run(
            user_id=SINGLETON_USER_ID,
            task_id="market_entry",
            goal="Enter EU EV-charging market",
            status=status,
        )
        session.add(run)
        await session.flush()
        session.add(
            Artifact(
                run_id=run.id,
                path="framing/questionnaire.json",
                kind="json",
                content='{"items": []}',
            )
        )
        await session.commit()
        await session.refresh(run)
        return run


async def _wait_for(predicate: callable, *, timeout: float = 3.0) -> None:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        if await predicate():
            return
        await asyncio.sleep(0.05)
    raise AssertionError("condition not met before timeout")


class _FactoryBarrier:
    def __init__(self) -> None:
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def __call__(self, _run_id: object) -> Callable[[str], object]:
        self.entered.set()
        await self.release.wait()

        def factory(_role: str) -> object:
            raise AssertionError("factory should not be used in startup race tests")

        return factory


@pytest.mark.asyncio
async def test_continue_after_framing_fails_when_timeout_budget_is_exceeded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RUN_TIMEOUT_SECONDS", "2")
    monkeypatch.setenv("HEARTBEAT_INTERVAL_SECONDS", "1")
    get_settings.cache_clear()

    run = await _create_run()
    run_id = run.id

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

    run = await _create_run()
    run_id = run.id

    class BlockingStructuredModel:
        def with_structured_output(self, _schema: object) -> BlockingStructuredModel:
            return self

        async def ainvoke(self, _messages: object) -> object:
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

    def factory(_role: str) -> object:
        return BlockingStructuredModel()

    async def flip_to_cancelling() -> None:
        async def _started() -> bool:
            async with AsyncSessionLocal() as session:
                run = await session.get(Run, run_id)
                return run is not None and run.started_at is not None

        await _wait_for(_started)
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


@pytest.mark.asyncio
async def test_continue_after_framing_preserves_persisted_cancelling_before_startup() -> None:
    run = await _create_run(status=RunStatus.cancelling)

    def factory(_role: str) -> object:
        raise AssertionError("worker must not start models for an already cancelling run")

    await continue_after_framing(
        run.id,
        answers={"time_horizon": "12 months"},
        profile=MARKET_ENTRY_PROFILE,
        model_factory=factory,
    )

    async with AsyncSessionLocal() as session:
        persisted = await session.get(Run, run.id)
        assert persisted is not None
        messages = (
            (await session.execute(select(Message).where(Message.run_id == run.id))).scalars().all()
        )

    assert persisted.status == RunStatus.cancelled
    assert persisted.started_at is None
    assert persisted.completed_at is not None
    assert messages == []


@pytest.mark.asyncio
async def test_continue_after_framing_marks_cancelled_when_task_is_cancelled_during_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_settings.cache_clear()
    run = await _create_run()
    barrier = _FactoryBarrier()
    monkeypatch.setattr(run_worker, "default_model_factory", barrier)

    task = asyncio.create_task(
        continue_after_framing(
            run.id,
            answers={"time_horizon": "12 months"},
            profile=MARKET_ENTRY_PROFILE,
            model_factory=None,
        )
    )

    try:
        await asyncio.wait_for(barrier.entered.wait(), timeout=2.0)
        task.cancel()
        await task

        async def _terminal() -> bool:
            async with AsyncSessionLocal() as session:
                persisted = await session.get(Run, run.id)
                return persisted is not None and persisted.status == RunStatus.cancelled

        await _wait_for(_terminal)

        async with AsyncSessionLocal() as session:
            persisted = await session.get(Run, run.id)
            assert persisted is not None

        assert persisted.completed_at is not None
    finally:
        barrier.release.set()
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_continue_after_framing_preserves_concurrent_cancel_during_startup_transition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_settings.cache_clear()
    run = await _create_run()
    transition_ready = asyncio.Event()
    allow_transition = asyncio.Event()
    original_execute = AsyncSession.execute

    class NoopModel:
        def with_structured_output(self, _schema: object) -> NoopModel:
            return self

        async def ainvoke(self, _messages: object) -> object:
            raise AssertionError("graph should not start after concurrent cancellation")

    def factory(_role: str) -> object:
        return NoopModel()

    async def gated_execute(
        self: object,
        statement: object,
        *args: object,
        **kwargs: object,
    ) -> object:
        table = getattr(statement, "table", None)
        if getattr(table, "name", None) == Run.__tablename__ and not transition_ready.is_set():
            transition_ready.set()
            await allow_transition.wait()
        return await original_execute(self, statement, *args, **kwargs)

    monkeypatch.setattr(AsyncSession, "execute", gated_execute)

    task = asyncio.create_task(
        continue_after_framing(
            run.id,
            answers={"time_horizon": "12 months"},
            profile=MARKET_ENTRY_PROFILE,
            model_factory=factory,
        )
    )

    try:
        await asyncio.wait_for(transition_ready.wait(), timeout=2.0)

        async with AsyncSessionLocal() as session:
            persisted = await session.get(Run, run.id)
            assert persisted is not None
            persisted.status = RunStatus.cancelling
            await session.commit()

        allow_transition.set()
        await task

        async with AsyncSessionLocal() as session:
            persisted = await session.get(Run, run.id)
            assert persisted is not None
            messages = (
                (await session.execute(select(Message).where(Message.run_id == run.id)))
                .scalars()
                .all()
            )

        assert persisted.status == RunStatus.cancelled
        assert persisted.started_at is None
        assert persisted.completed_at is not None
        assert messages == []
    finally:
        allow_transition.set()
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        get_settings.cache_clear()

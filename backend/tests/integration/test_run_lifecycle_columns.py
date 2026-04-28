"""Integration tests for run lifecycle ORM fields and schema migration."""

from __future__ import annotations

import asyncio
import contextlib

import pytest
from sqlalchemy import text

from app.agents.market_entry.profile import MARKET_ENTRY_PROFILE
from app.core.config import get_settings
from app.core.db import AsyncSessionLocal
from app.models import SINGLETON_USER_ID, Artifact, Run, RunStatus
from app.workers.run_worker import continue_after_framing


async def _wait_for(predicate: callable, *, timeout: float = 3.0) -> None:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        if await predicate():
            return
        await asyncio.sleep(0.05)
    raise AssertionError("condition not met before timeout")


def test_run_model_exposes_lifecycle_fields() -> None:
    columns = Run.__table__.c

    assert "started_at" in columns
    assert columns.started_at.nullable is True
    assert "completed_at" in columns
    assert columns.completed_at.nullable is True
    assert "heartbeat_at" in columns
    assert columns.heartbeat_at.nullable is True


async def test_runs_table_has_nullable_lifecycle_columns_and_partial_index() -> None:
    session = AsyncSessionLocal()
    try:
        column_rows = (
            (
                await session.execute(
                    text(
                        """
                    SELECT column_name, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'runs'
                      AND column_name IN ('started_at', 'completed_at', 'heartbeat_at')
                    ORDER BY column_name
                    """
                    )
                )
            )
            .mappings()
            .all()
        )

        assert column_rows == [
            {
                "column_name": "completed_at",
                "is_nullable": "YES",
                "column_default": None,
            },
            {
                "column_name": "heartbeat_at",
                "is_nullable": "YES",
                "column_default": None,
            },
            {
                "column_name": "started_at",
                "is_nullable": "YES",
                "column_default": None,
            },
        ]

        indexdef = await session.scalar(
            text(
                """
                SELECT indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename = 'runs'
                  AND indexname = 'ix_runs_status_heartbeat'
                """
            )
        )

        assert indexdef is not None
        expected_index = (
            "CREATE INDEX ix_runs_status_heartbeat ON public.runs USING btree "
            "(status, heartbeat_at)"
        )
        assert expected_index in indexdef
        assert "WHERE (status = 'running'::run_status)" in indexdef
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_continue_after_framing_populates_lifecycle_timestamps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    task = asyncio.create_task(
        continue_after_framing(
            run_id,
            answers={"time_horizon": "12 months"},
            profile=MARKET_ENTRY_PROFILE,
            model_factory=factory,
        )
    )

    try:
        started_at = None

        async def _started() -> bool:
            nonlocal started_at
            async with AsyncSessionLocal() as session:
                run = await session.get(Run, run_id)
                assert run is not None
                if run.started_at is not None:
                    started_at = run.started_at
                    return True
                return False

        await _wait_for(_started, timeout=2.0)

        assert started_at is not None

        first_heartbeat = None

        async def _heartbeat_started() -> bool:
            nonlocal first_heartbeat
            async with AsyncSessionLocal() as session:
                run = await session.get(Run, run_id)
                assert run is not None
                if run.heartbeat_at is not None and run.heartbeat_at > started_at:
                    first_heartbeat = run.heartbeat_at
                    return True
                return False

        await _wait_for(_heartbeat_started, timeout=2.5)

        second_heartbeat = None

        async def _heartbeat_advanced() -> bool:
            nonlocal second_heartbeat
            async with AsyncSessionLocal() as session:
                run = await session.get(Run, run_id)
                assert run is not None
                if first_heartbeat is not None and run.heartbeat_at is not None:
                    if run.heartbeat_at > first_heartbeat:
                        second_heartbeat = run.heartbeat_at
                        return True
                return False

        await _wait_for(_heartbeat_advanced, timeout=2.5)

        async with AsyncSessionLocal() as session:
            run = await session.get(Run, run_id)
            assert run is not None
            assert run.status == RunStatus.running
            assert run.started_at is not None
            assert run.started_at == started_at
            assert first_heartbeat is not None
            assert second_heartbeat is not None
            assert run.heartbeat_at == second_heartbeat

        task.cancel()
        await task

        async with AsyncSessionLocal() as session:
            run = await session.get(Run, run_id)
            assert run is not None
            assert run.status == RunStatus.cancelled
            assert run.started_at is not None
            assert run.heartbeat_at is not None
            assert run.completed_at is not None
            assert run.completed_at >= run.started_at
    finally:
        if not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        get_settings.cache_clear()

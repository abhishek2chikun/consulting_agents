"""Integration tests for stale-run recovery sweeper."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.agents._engine.recovery import sweep_stale_runs
from app.core.config import get_settings
from app.core.db import AsyncSessionLocal
from app.main import create_app
from app.models import SINGLETON_USER_ID, Event, Run, RunStatus


async def _create_run(
    *,
    status: RunStatus,
    heartbeat_at: datetime | None = None,
    started_at: datetime | None = None,
) -> Run:
    async with AsyncSessionLocal() as session:
        run = Run(
            user_id=SINGLETON_USER_ID,
            task_id="market_entry",
            goal="Recover stale run",
            status=status,
            started_at=started_at,
            heartbeat_at=heartbeat_at,
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        return run


@pytest.mark.asyncio
async def test_sweep_stale_runs_fails_stale_running_rows() -> None:
    settings = get_settings()
    now = datetime.now(UTC)
    stale_heartbeat = now - timedelta(seconds=settings.stale_run_threshold_seconds + 1)
    run = await _create_run(
        status=RunStatus.running,
        started_at=stale_heartbeat - timedelta(minutes=1),
        heartbeat_at=stale_heartbeat,
    )

    recovered = await sweep_stale_runs()

    async with AsyncSessionLocal() as session:
        persisted = await session.get(Run, run.id)
        events = (
            (await session.execute(select(Event).where(Event.run_id == run.id).order_by(Event.id)))
            .scalars()
            .all()
        )

    assert recovered >= 1
    assert persisted is not None
    assert persisted.status == RunStatus.failed
    assert persisted.completed_at is not None
    assert persisted.completed_at >= persisted.heartbeat_at
    assert len(events) == 1
    assert events[0].type == "run_failed"
    assert events[0].agent == "system"
    assert events[0].payload == {"reason": "staleness: no heartbeat for >5 minutes"}


@pytest.mark.asyncio
async def test_sweep_stale_runs_leaves_non_stale_and_non_running_rows_untouched() -> None:
    settings = get_settings()
    now = datetime.now(UTC)
    fresh_running = await _create_run(
        status=RunStatus.running,
        started_at=now - timedelta(minutes=2),
        heartbeat_at=now - timedelta(seconds=settings.stale_run_threshold_seconds - 1),
    )
    created_run = await _create_run(
        status=RunStatus.created,
        heartbeat_at=now - timedelta(seconds=settings.stale_run_threshold_seconds + 60),
    )
    completed_run = await _create_run(
        status=RunStatus.completed,
        started_at=now - timedelta(minutes=10),
        heartbeat_at=now - timedelta(minutes=8),
    )

    recovered = await sweep_stale_runs()

    async with AsyncSessionLocal() as session:
        fresh_persisted = await session.get(Run, fresh_running.id)
        created_persisted = await session.get(Run, created_run.id)
        completed_persisted = await session.get(Run, completed_run.id)
        events = (
            (
                await session.execute(
                    select(Event)
                    .where(Event.run_id.in_([fresh_running.id, created_run.id, completed_run.id]))
                    .order_by(Event.id)
                )
            )
            .scalars()
            .all()
        )

    assert recovered == 0
    assert fresh_persisted is not None
    assert fresh_persisted.status == RunStatus.running
    assert fresh_persisted.completed_at is None
    assert created_persisted is not None
    assert created_persisted.status == RunStatus.created
    assert created_persisted.completed_at is None
    assert completed_persisted is not None
    assert completed_persisted.status == RunStatus.completed
    assert completed_persisted.completed_at is None
    assert events == []


@pytest.mark.asyncio
async def test_app_startup_runs_stale_run_sweeper(monkeypatch: pytest.MonkeyPatch) -> None:
    sweeper = AsyncMock(return_value=0)
    monkeypatch.setattr("app.main.sweep_stale_runs", sweeper)

    app = create_app()
    async with app.router.lifespan_context(app):
        pass

    sweeper.assert_awaited_once_with()

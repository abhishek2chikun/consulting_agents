"""Integration tests for stale-run recovery sweeper."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select, update

from app.agents._engine.recovery import _staleness_reason, sweep_stale_runs
from app.core.config import get_settings
from app.core.db import AsyncSessionLocal
from app.main import create_app
from app.models import SINGLETON_USER_ID, Event, Run, RunStatus


async def _create_run(
    *,
    status: RunStatus,
    heartbeat_at: datetime | None = None,
    started_at: datetime | None = None,
    created_at: datetime | None = None,
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
        if created_at is not None:
            await session.execute(update(Run).where(Run.id == run.id).values(created_at=created_at))
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
    assert events[0].type == "system.run_failed"
    assert events[0].agent == "system"
    assert events[0].payload == {"reason": _staleness_reason(settings.stale_run_threshold_seconds)}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("started_at", "created_at"),
    [
        pytest.param("stale", None, id="falls-back-to-started-at"),
        pytest.param(None, "stale", id="falls-back-to-created-at"),
    ],
)
async def test_sweep_stale_runs_falls_back_when_heartbeat_is_null(
    started_at: str | None,
    created_at: str | None,
) -> None:
    settings = get_settings()
    stale_timestamp = datetime.now(UTC) - timedelta(
        seconds=settings.stale_run_threshold_seconds + 1
    )
    run = await _create_run(
        status=RunStatus.running,
        started_at=stale_timestamp if started_at == "stale" else None,
        heartbeat_at=None,
        created_at=stale_timestamp if created_at == "stale" else None,
    )

    if created_at == "stale":
        async with AsyncSessionLocal() as session:
            persisted = await session.get(Run, run.id)
            assert persisted is not None
            assert persisted.created_at == stale_timestamp

    recovered = await sweep_stale_runs()

    async with AsyncSessionLocal() as session:
        persisted = await session.get(Run, run.id)
        events = (
            (await session.execute(select(Event).where(Event.run_id == run.id).order_by(Event.id)))
            .scalars()
            .all()
        )

    assert recovered == 1
    assert persisted is not None
    assert persisted.status == RunStatus.failed
    assert len(events) == 1
    assert events[0].type == "system.run_failed"


@pytest.mark.asyncio
async def test_sweep_stale_runs_is_idempotent_after_first_recovery() -> None:
    settings = get_settings()
    stale_heartbeat = datetime.now(UTC) - timedelta(
        seconds=settings.stale_run_threshold_seconds + 1
    )
    run = await _create_run(
        status=RunStatus.running,
        started_at=stale_heartbeat - timedelta(minutes=1),
        heartbeat_at=stale_heartbeat,
    )

    first_recovered = await sweep_stale_runs()
    second_recovered = await sweep_stale_runs()

    async with AsyncSessionLocal() as session:
        events = (
            (await session.execute(select(Event).where(Event.run_id == run.id).order_by(Event.id)))
            .scalars()
            .all()
        )

    assert first_recovered == 1
    assert second_recovered == 0
    assert len(events) == 1


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

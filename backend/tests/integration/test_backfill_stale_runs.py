"""Integration tests for the orphaned stale-run backfill script."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, update

from app.core.db import AsyncSessionLocal
from app.models import SINGLETON_USER_ID, Event, Run, RunStatus
from scripts.backfill_stale_runs import BACKFILL_RATIONALE, backfill_stale_runs, main_async


async def _create_run(*, status: RunStatus, created_at: datetime | None = None) -> Run:
    async with AsyncSessionLocal() as session:
        run = Run(
            user_id=SINGLETON_USER_ID,
            task_id="market_entry",
            goal="Backfill stale run",
            status=status,
        )
        session.add(run)
        await session.commit()
        if created_at is not None:
            await session.execute(update(Run).where(Run.id == run.id).values(created_at=created_at))
            await session.commit()
        await session.refresh(run)
        return run


async def _count_stale_running_runs() -> int:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(func.count())
            .select_from(Run)
            .where(
                Run.status == RunStatus.running,
                Run.created_at < datetime.now(UTC) - timedelta(hours=24),
            )
        )
        return int(result.scalar_one())


@pytest.mark.asyncio
async def test_backfill_stale_runs_marks_stale_running_rows_failed_and_inserts_event() -> None:
    stale_run = await _create_run(
        status=RunStatus.running,
        created_at=datetime.now(UTC) - timedelta(hours=25),
    )
    expected_updates = await _count_stale_running_runs()

    updated = await backfill_stale_runs()

    async with AsyncSessionLocal() as session:
        persisted = await session.get(Run, stale_run.id)
        events = (
            (
                await session.execute(
                    select(Event).where(Event.run_id == stale_run.id).order_by(Event.id)
                )
            )
            .scalars()
            .all()
        )

    assert updated == expected_updates
    assert persisted is not None
    assert persisted.status == RunStatus.failed
    assert persisted.completed_at is not None
    assert len(events) == 1
    assert events[0].type == "system.run_failed"
    assert events[0].agent == "system"
    assert events[0].payload == {"rationale": BACKFILL_RATIONALE}


@pytest.mark.asyncio
async def test_backfill_stale_runs_leaves_fresh_running_rows_untouched() -> None:
    fresh_run = await _create_run(
        status=RunStatus.running,
        created_at=datetime.now(UTC) - timedelta(hours=23, minutes=59),
    )
    expected_updates = await _count_stale_running_runs()

    updated = await backfill_stale_runs()

    async with AsyncSessionLocal() as session:
        persisted = await session.get(Run, fresh_run.id)
        events = (
            (
                await session.execute(
                    select(Event).where(Event.run_id == fresh_run.id).order_by(Event.id)
                )
            )
            .scalars()
            .all()
        )

    assert updated == expected_updates
    assert persisted is not None
    assert persisted.status == RunStatus.running
    assert persisted.completed_at is None
    assert events == []


@pytest.mark.asyncio
async def test_backfill_stale_runs_is_idempotent_on_rerun() -> None:
    stale_run = await _create_run(
        status=RunStatus.running,
        created_at=datetime.now(UTC) - timedelta(hours=26),
    )
    expected_updates = await _count_stale_running_runs()

    first_updated = await backfill_stale_runs()
    second_updated = await backfill_stale_runs()

    async with AsyncSessionLocal() as session:
        events = (
            (
                await session.execute(
                    select(Event).where(Event.run_id == stale_run.id).order_by(Event.id)
                )
            )
            .scalars()
            .all()
        )

    assert first_updated == expected_updates
    assert second_updated == 0
    assert len(events) == 1


@pytest.mark.asyncio
async def test_backfill_stale_runs_dry_run_reports_count_without_mutating_db(
    capsys: pytest.CaptureFixture[str],
) -> None:
    stale_run = await _create_run(
        status=RunStatus.running,
        created_at=datetime.now(UTC) - timedelta(hours=27),
    )
    expected_updates = await _count_stale_running_runs()

    updated = await backfill_stale_runs(dry_run=True)
    exit_code = await main_async(["--dry-run"])
    captured = capsys.readouterr()

    async with AsyncSessionLocal() as session:
        persisted = await session.get(Run, stale_run.id)
        events = (
            (
                await session.execute(
                    select(Event).where(Event.run_id == stale_run.id).order_by(Event.id)
                )
            )
            .scalars()
            .all()
        )

    assert updated == expected_updates
    assert exit_code == 0
    assert f"{expected_updates} stale running runs would be backfilled" in captured.out
    assert persisted is not None
    assert persisted.status == RunStatus.running
    assert persisted.completed_at is None
    assert events == []

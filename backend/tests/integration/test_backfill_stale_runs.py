"""Integration tests for the orphaned stale-run backfill script."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update

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


async def _load_runs(*run_ids: Run) -> dict[str, Run]:
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(select(Run).where(Run.id.in_([run.id for run in run_ids])))
        ).scalars()
        return {str(run.id): run for run in rows}


async def _load_events(*run_ids: Run) -> dict[str, list[Event]]:
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(Event)
                .where(Event.run_id.in_([run.id for run in run_ids]))
                .order_by(Event.run_id, Event.id)
            )
        ).scalars()
        grouped: dict[str, list[Event]] = {str(run.id): [] for run in run_ids}
        for event in rows:
            grouped[str(event.run_id)].append(event)
        return grouped


def _assert_single_failure_event(events: Iterable[Event]) -> None:
    rows = list(events)
    assert len(rows) == 1
    assert rows[0].type == "system.run_failed"
    assert rows[0].agent == "system"
    assert rows[0].payload == {"reason": BACKFILL_RATIONALE}


@pytest.mark.asyncio
async def test_backfill_stale_runs_marks_stale_running_rows_failed_and_inserts_event() -> None:
    stale_run = await _create_run(
        status=RunStatus.running,
        created_at=datetime.now(UTC) - timedelta(hours=25),
    )

    updated = await backfill_stale_runs()

    persisted = (await _load_runs(stale_run))[str(stale_run.id)]
    events = (await _load_events(stale_run))[str(stale_run.id)]

    assert updated >= 1
    assert persisted.status == RunStatus.failed
    assert persisted.completed_at is not None
    _assert_single_failure_event(events)


@pytest.mark.asyncio
async def test_backfill_stale_runs_leaves_fresh_running_rows_untouched() -> None:
    stale_run = await _create_run(
        status=RunStatus.running,
        created_at=datetime.now(UTC) - timedelta(hours=25),
    )
    fresh_run = await _create_run(
        status=RunStatus.running,
        created_at=datetime.now(UTC) - timedelta(hours=23, minutes=59),
    )

    updated = await backfill_stale_runs()

    persisted = await _load_runs(stale_run, fresh_run)
    events = await _load_events(stale_run, fresh_run)

    assert updated >= 1
    assert persisted[str(stale_run.id)].status == RunStatus.failed
    assert persisted[str(stale_run.id)].completed_at is not None
    _assert_single_failure_event(events[str(stale_run.id)])
    assert persisted[str(fresh_run.id)].status == RunStatus.running
    assert persisted[str(fresh_run.id)].completed_at is None
    assert events[str(fresh_run.id)] == []


@pytest.mark.asyncio
async def test_backfill_stale_runs_is_idempotent_on_rerun() -> None:
    stale_run = await _create_run(
        status=RunStatus.running,
        created_at=datetime.now(UTC) - timedelta(hours=26),
    )

    first_updated = await backfill_stale_runs()
    second_updated = await backfill_stale_runs()

    events = (await _load_events(stale_run))[str(stale_run.id)]

    assert first_updated >= 1
    assert second_updated == 0
    _assert_single_failure_event(events)


@pytest.mark.asyncio
async def test_backfill_stale_runs_dry_run_reports_count_without_mutating_db(
    capsys: pytest.CaptureFixture[str],
) -> None:
    stale_run = await _create_run(
        status=RunStatus.running,
        created_at=datetime.now(UTC) - timedelta(hours=27),
    )

    updated = await backfill_stale_runs(dry_run=True)
    exit_code = await main_async(["--dry-run"])
    captured = capsys.readouterr()

    persisted = (await _load_runs(stale_run))[str(stale_run.id)]
    events = (await _load_events(stale_run))[str(stale_run.id)]

    assert updated >= 1
    assert exit_code == 0
    assert f"{updated} stale running runs would be backfilled" in captured.out
    assert persisted.status == RunStatus.running
    assert persisted.completed_at is None
    assert events == []

"""Startup recovery helpers for orphaned running runs."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import AsyncSessionLocal
from app.core.events import publish
from app.models import Run, RunStatus


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _staleness_reason(threshold_seconds: int) -> str:
    threshold_minutes = threshold_seconds // 60
    if threshold_seconds % 60 == 0 and threshold_minutes > 0:
        unit = "minute" if threshold_minutes == 1 else "minutes"
        return f"staleness: no heartbeat for >{threshold_minutes} {unit}"
    unit = "second" if threshold_seconds == 1 else "seconds"
    return f"staleness: no heartbeat for >{threshold_seconds} {unit}"


async def sweep_stale_runs(session: AsyncSession | None = None) -> int:
    """Mark stale running rows as failed and emit failure events."""
    owns_session = session is None
    active_session = session or AsyncSessionLocal()
    settings = get_settings()
    cutoff = _utcnow() - timedelta(seconds=settings.stale_run_threshold_seconds)
    reason = _staleness_reason(settings.stale_run_threshold_seconds)

    try:
        stale_runs = (
            (
                await active_session.execute(
                    select(Run).where(
                        Run.status == RunStatus.running,
                        Run.heartbeat_at.is_not(None),
                        Run.heartbeat_at < cutoff,
                    )
                )
            )
            .scalars()
            .all()
        )

        if not stale_runs:
            return 0

        completed_at = _utcnow()
        run_ids: list[uuid.UUID] = []
        for run in stale_runs:
            run.status = RunStatus.failed
            run.completed_at = completed_at
            run_ids.append(run.id)

        await active_session.commit()

        for run_id in run_ids:
            await publish(run_id, "system.run_failed", {"reason": reason}, agent="system")

        return len(run_ids)
    finally:
        if owns_session:
            await active_session.close()


__all__ = ["sweep_stale_runs"]

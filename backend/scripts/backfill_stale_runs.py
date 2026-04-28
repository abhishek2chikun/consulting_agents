"""One-off backfill for orphaned V1.5 stale runs."""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionLocal
from app.models import Event, Run, RunStatus

BACKFILL_RATIONALE = "backfill: orphaned by V1.5 worker"
BACKFILL_EVENT_TYPE = "system.run_failed"
BACKFILL_AGENT = "system"
BACKFILL_WINDOW = timedelta(hours=24)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report how many stale running rows would be backfilled without mutating the DB",
    )
    return parser


async def backfill_stale_runs(*, dry_run: bool = False, session: AsyncSession | None = None) -> int:
    """Mark orphaned stale running rows failed and append one failure event each."""
    owns_session = session is None
    active_session = session or AsyncSessionLocal()
    cutoff = _utcnow() - BACKFILL_WINDOW

    try:
        run_ids = list(
            (
                await active_session.execute(
                    select(Run.id)
                    .where(
                        Run.status == RunStatus.running,
                        Run.created_at < cutoff,
                    )
                    .order_by(Run.created_at, Run.id)
                )
            )
            .scalars()
            .all()
        )

        if dry_run or not run_ids:
            return len(run_ids)

        completed_at = _utcnow()
        transitioned_run_ids = list(
            (
                await active_session.execute(
                    update(Run)
                    .where(
                        Run.id.in_(run_ids),
                        Run.status == RunStatus.running,
                    )
                    .values(status=RunStatus.failed, completed_at=completed_at)
                    .returning(Run.id)
                )
            )
            .scalars()
            .all()
        )

        if transitioned_run_ids:
            await active_session.execute(
                insert(Event),
                [
                    {
                        "run_id": run_id,
                        "type": BACKFILL_EVENT_TYPE,
                        "agent": BACKFILL_AGENT,
                        "payload": {"rationale": BACKFILL_RATIONALE},
                    }
                    for run_id in transitioned_run_ids
                ],
            )

        await active_session.commit()
        return len(transitioned_run_ids)
    finally:
        if owns_session:
            await active_session.close()


async def main_async(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)
    updated = await backfill_stale_runs(dry_run=args.dry_run)
    if args.dry_run:
        print(f"{updated} stale running runs would be backfilled")
    else:
        print(f"{updated} stale running runs backfilled")
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(main_async()))


if __name__ == "__main__":
    main()

"""Worker entrypoint for the M&A V2 stub (M8.1).

Mirrors the shape of `app.workers.run_worker.continue_after_framing`
but for a single-step graph that takes no human input — selecting
"M&A" in the UI directly dispatches here from the run worker / API
layer.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from app.core.db import AsyncSessionLocal
from app.core.events import publish
from app.models import Run, RunStatus

from .graph import build_graph

logger = logging.getLogger(__name__)


async def run_ma_stub(run_id: uuid.UUID) -> None:
    """Drive the one-node M&A stub graph end-to-end.

    Reads the run goal from Postgres, sets `Run.status -> running`,
    streams the placeholder node, and lets the node itself transition
    to `completed`. Failures mark the run failed and publish
    `run_failed`.
    """
    async with AsyncSessionLocal() as session:
        run = await session.get(Run, run_id)
        if run is None:
            return
        run.status = RunStatus.running
        goal = run.goal
        await session.commit()

    initial: dict[str, Any] = {"run_id": str(run_id), "goal": goal}
    graph = build_graph()
    try:
        async for _chunk in graph.astream(initial):  # type: ignore[attr-defined]
            pass
    except Exception as exc:
        logger.exception("M&A stub graph failed for run %s", run_id)
        async with AsyncSessionLocal() as session:
            run = await session.get(Run, run_id)
            if run is not None:
                run.status = RunStatus.failed
                await session.commit()
        await publish(run_id, "run_failed", {"reason": str(exc)}, agent="system")


__all__ = ["run_ma_stub"]

"""In-process registry of background asyncio.Tasks keyed by string ID.

V1 deliberately runs background work (ingest, agent runs) inside the
FastAPI process — no Celery, no Redis. The registry exists so that a
later request handler (cancel an in-flight ingest, abort a pipeline run)
can look up the live `asyncio.Task` and `.cancel()` it.

Scope and constraints:
- Single event loop. The registry is **not** thread-safe; FastAPI's
  uvicorn worker is single-threaded for async handlers, which matches.
- Backend restart cancels every in-flight task — there is no on-disk
  resume. Callers that care about durability mark progress in the DB
  before yielding (e.g. `Document.status` transitions in `run_ingest`).
- Completed tasks remove themselves via a done-callback so the dict
  doesn't grow without bound across long-lived processes.

The module exports a process-wide singleton `TASK_REGISTRY` for code
that needs to schedule a tracked task (`POST /documents` →
`run_ingest`). Tests should construct their own `TaskRegistry()` to
avoid polluting the singleton.
"""

from __future__ import annotations

import asyncio
from typing import Final


class TaskRegistry:
    """Maps a string key to an `asyncio.Task` so it can be looked up later."""

    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[None]] = {}

    def register(self, key: str, task: asyncio.Task[None]) -> None:
        """Track `task` under `key`.

        If `key` already maps to a task, the new entry overwrites it
        silently — callers wanting graceful replacement should
        `cancel(key)` first. The done-callback is anchored to the
        specific task object so a later overwrite doesn't trigger a
        spurious removal of the new entry when the old task finishes.
        """
        self._tasks[key] = task

        def _cleanup(t: asyncio.Task[None], k: str = key) -> None:
            # Only remove if the entry still points to the task that fired
            # the callback; otherwise we'd erase a fresh registration.
            if self._tasks.get(k) is t:
                self._tasks.pop(k, None)

        task.add_done_callback(_cleanup)

    def get(self, key: str) -> asyncio.Task[None] | None:
        """Return the task registered under `key`, or `None`."""
        return self._tasks.get(key)

    def cancel(self, key: str) -> bool:
        """Request cancellation of `key`'s task.

        Returns True if a live (not-already-done) task was found and
        `.cancel()` was called on it; False if the key is unknown or the
        task already completed.
        """
        task = self._tasks.get(key)
        if task is None or task.done():
            return False
        task.cancel()
        return True

    def keys(self) -> list[str]:
        """Snapshot of currently-registered keys."""
        return list(self._tasks.keys())


TASK_REGISTRY: Final[TaskRegistry] = TaskRegistry()


__all__ = ["TASK_REGISTRY", "TaskRegistry"]

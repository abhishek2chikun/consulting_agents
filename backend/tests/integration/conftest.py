"""Shared fixtures for integration tests.

Drains any background `ingest:*` tasks that the documents API may have
scheduled during the test. Pre-M3.6, `POST /documents` returned 201 and
did nothing else; from M3.6 onwards it kicks off `run_ingest` as a
background `asyncio.Task`. Existing M3.3 tests upload PDFs without
configuring an OpenAI key, so the background ingest will (correctly)
transition the row to `failed`. Without this fixture, those tasks would
still be running when the next test starts and would log noise (and
possibly hold DB connections open across event-loop boundaries on the
shared session-scoped loop).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest

from app.core.task_registry import TASK_REGISTRY


@pytest.fixture(autouse=True)
async def _drain_ingest_tasks() -> AsyncIterator[None]:
    """After every integration test, wait for (or cancel) ingest tasks."""
    yield
    # Snapshot so we don't iterate while the registry mutates underneath us.
    keys = [k for k in TASK_REGISTRY.keys() if k.startswith("ingest:") or k.startswith("run:")]
    for k in keys:
        task = TASK_REGISTRY.get(k)
        if task is None or task.done():
            continue
        # Give the task a brief grace period to finish naturally
        # (settings-key lookup + transition to `failed` is fast).
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=2.0)
        except (TimeoutError, asyncio.CancelledError):
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        except Exception:  # noqa: BLE001
            # Task itself swallowed via the worker's broad except, but
            # in case anything propagates here, ignore — the test
            # already asserted what it cared about.
            pass

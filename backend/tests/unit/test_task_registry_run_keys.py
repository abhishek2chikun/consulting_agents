"""Task registry behavior for run-keyed tasks (M5.5)."""

from __future__ import annotations

import asyncio
import uuid

import pytest

from app.core.task_registry import TaskRegistry


@pytest.mark.asyncio
async def test_spawn_registers_task_under_run_key() -> None:
    registry = TaskRegistry()
    run_id = uuid.uuid4()
    key = f"run:{run_id}"

    done = asyncio.Event()

    async def _worker() -> None:
        done.set()

    task = registry.spawn(key, _worker())

    await asyncio.wait_for(done.wait(), timeout=1.0)
    await task
    await asyncio.sleep(0)

    assert task.done()
    assert registry.get(key) is None

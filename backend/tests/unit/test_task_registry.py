"""Tests for the in-process asyncio task registry (M3.6).

The registry is a thin dict wrapper used by the ingest worker (and later
the pipeline runner in M6) to track background `asyncio.Task`s by string
key so they can be cancelled or inspected.
"""

from __future__ import annotations

import asyncio

import pytest

from app.core.task_registry import TASK_REGISTRY, TaskRegistry


@pytest.fixture
def registry() -> TaskRegistry:
    """Fresh registry per test (don't pollute the module-level singleton)."""
    return TaskRegistry()


async def test_register_and_get_returns_same_task(registry: TaskRegistry) -> None:
    async def sleeper() -> None:
        await asyncio.sleep(10)

    task = asyncio.create_task(sleeper())
    registry.register("k1", task)
    try:
        assert registry.get("k1") is task
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


async def test_cancel_running_task_returns_true(registry: TaskRegistry) -> None:
    async def sleeper() -> None:
        await asyncio.sleep(10)

    task = asyncio.create_task(sleeper())
    registry.register("k", task)

    assert registry.cancel("k") is True

    # Allow cancellation to propagate.
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert task.cancelled()


async def test_cancel_unknown_key_returns_false(registry: TaskRegistry) -> None:
    assert registry.cancel("does-not-exist") is False


async def test_completed_task_auto_removed(registry: TaskRegistry) -> None:
    async def quick() -> None:
        return None

    task = asyncio.create_task(quick())
    registry.register("done", task)
    await task
    # Yield once more so the done-callback runs.
    await asyncio.sleep(0)
    assert registry.get("done") is None
    assert "done" not in registry.keys()


async def test_overwrite_existing_key(registry: TaskRegistry) -> None:
    async def sleeper() -> None:
        await asyncio.sleep(10)

    t1 = asyncio.create_task(sleeper())
    t2 = asyncio.create_task(sleeper())
    registry.register("dup", t1)
    registry.register("dup", t2)
    try:
        assert registry.get("dup") is t2
    finally:
        for t in (t1, t2):
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass


async def test_module_level_singleton_exists() -> None:
    """The module exports a process-wide TASK_REGISTRY instance."""
    assert isinstance(TASK_REGISTRY, TaskRegistry)

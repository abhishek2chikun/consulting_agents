"""Integration tests for `/runs/{id}/stream` SSE endpoint (M5.3)."""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy import delete

from app.core.db import AsyncSessionLocal
from app.core.events import publish
from app.main import create_app
from app.models import SINGLETON_USER_ID, Run, RunStatus


async def _seed_run(run_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        session.add(
            Run(
                id=run_id,
                user_id=SINGLETON_USER_ID,
                task_id="market_entry",
                goal="sse-test",
                status=RunStatus.created,
                model_snapshot={},
            )
        )
        await session.commit()


async def _cleanup_run(run_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(delete(Run).where(Run.id == run_id))
        await session.commit()


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _collect_event_ids(
    response: httpx.Response,
    *,
    expected_count: int,
    timeout: float = 3.0,
) -> list[int]:
    ids: list[int] = []
    deadline = asyncio.get_event_loop().time() + timeout

    line_iter = response.aiter_lines()
    while len(ids) < expected_count:
        remaining = deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            break
        try:
            line = await asyncio.wait_for(anext(line_iter), timeout=remaining)
        except (StopAsyncIteration, TimeoutError):
            break
        if line.startswith("id: "):
            ids.append(int(line.removeprefix("id: ").strip()))
    return ids


@pytest.mark.asyncio
async def test_sse_stream_receives_events_in_order(client: httpx.AsyncClient) -> None:
    run_id = uuid.uuid4()
    await _seed_run(run_id)

    async def _publisher() -> None:
        await asyncio.sleep(0.1)
        for idx in range(3):
            await publish(run_id, "tick", {"n": idx})

    pub_task = asyncio.create_task(_publisher())
    try:
        async with client.stream("GET", f"/runs/{run_id}/stream?max_events=3") as response:
            assert response.status_code == 200
            ids = await _collect_event_ids(response, expected_count=3)

        assert len(ids) == 3
        assert ids == sorted(ids)
        await pub_task
    finally:
        if not pub_task.done():
            pub_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await pub_task
        await _cleanup_run(run_id)


@pytest.mark.asyncio
async def test_sse_stream_resumes_with_last_event_id(client: httpx.AsyncClient) -> None:
    run_id = uuid.uuid4()
    await _seed_run(run_id)

    try:
        first_id = await publish(run_id, "phase", {"n": 1})
        second_id = await publish(run_id, "phase", {"n": 2})

        # Reconnect after event 1: should replay event 2 first.
        async with client.stream(
            "GET",
            f"/runs/{run_id}/stream?max_events=1",
            headers={"Last-Event-ID": str(first_id)},
        ) as response:
            ids = await _collect_event_ids(response, expected_count=1)

        assert ids == [second_id]

        third_id = await publish(run_id, "phase", {"n": 3})
        fourth_id = await publish(run_id, "phase", {"n": 4})

        async with client.stream(
            "GET",
            f"/runs/{run_id}/stream?max_events=2",
            headers={"Last-Event-ID": str(second_id)},
        ) as response:
            resumed_ids = await _collect_event_ids(response, expected_count=2)

        assert resumed_ids == [third_id, fourth_id]
    finally:
        await _cleanup_run(run_id)

"""Integration tests for event publisher + LISTEN/NOTIFY (M5.2)."""

from __future__ import annotations

import asyncio
import uuid

import asyncpg
import pytest
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.db import AsyncSessionLocal
from app.core.events import channel_for_run, publish, subscribe
from app.models import SINGLETON_USER_ID, Event, Run, RunStatus


async def _cleanup_run(run_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(delete(Run).where(Run.id == run_id))
        await session.commit()


async def _seed_run(run_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        session.add(
            Run(
                id=run_id,
                user_id=SINGLETON_USER_ID,
                task_id="market_entry",
                goal="event-test",
                status=RunStatus.created,
                model_snapshot={},
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_publish_inserts_event_and_fires_notify() -> None:
    run_id = uuid.uuid4()
    await _seed_run(run_id)

    dsn = get_settings().database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn=dsn)
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=1)

    def _listener(_conn: asyncpg.Connection, _pid: int, _channel: str, payload: str) -> None:
        queue.put_nowait(payload)

    channel = channel_for_run(run_id)
    await conn.add_listener(channel, _listener)

    try:
        event_id = await publish(run_id, "artifact_update", {"path": "x.md"}, agent="framing")

        payload = await asyncio.wait_for(queue.get(), timeout=2.0)
        assert payload == str(event_id)

        async with AsyncSessionLocal() as session:
            row = await session.get(Event, event_id)
            assert row is not None
            assert row.run_id == run_id
            assert row.type == "artifact_update"
            assert row.payload == {"path": "x.md"}
            assert row.agent == "framing"
    finally:
        await conn.remove_listener(channel, _listener)
        await conn.close()
        await _cleanup_run(run_id)


@pytest.mark.asyncio
async def test_subscribe_replays_from_last_event_id() -> None:
    run_id = uuid.uuid4()
    await _seed_run(run_id)

    try:
        first_id = await publish(run_id, "one", {"n": 1})
        second_id = await publish(run_id, "two", {"n": 2})

        stream = subscribe(run_id, last_event_id=first_id)
        replayed = await asyncio.wait_for(anext(stream), timeout=2.0)
        await stream.aclose()

        assert replayed.id == second_id
        assert replayed.type == "two"
        assert replayed.payload == {"n": 2}

        async with AsyncSessionLocal() as session:
            rows = (
                await session.execute(
                    select(Event).where(Event.run_id == run_id).order_by(Event.id)
                )
            ).scalars()
            assert [r.id for r in rows] == [first_id, second_id]
    finally:
        await _cleanup_run(run_id)

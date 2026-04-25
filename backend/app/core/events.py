"""Run event publisher/subscriber with Postgres LISTEN/NOTIFY (M5.2)."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator

import asyncpg
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import AsyncSessionLocal
from app.models import Event


def channel_for_run(run_id: uuid.UUID) -> str:
    """Stable NOTIFY channel for a run-id."""
    return f"events_run_{str(run_id).replace('-', '_')}"


def _pg_dsn() -> str:
    return get_settings().database_url.replace("postgresql+asyncpg://", "postgresql://")


async def publish(
    run_id: uuid.UUID,
    type: str,
    payload: dict[str, object],
    agent: str | None = None,
) -> int:
    """Insert event row and emit NOTIFY with the new event id."""
    async with AsyncSessionLocal() as session:
        row = Event(run_id=run_id, type=type, payload=payload, agent=agent)
        session.add(row)
        await session.flush()
        event_id = row.id
        await session.commit()

    conn = await asyncpg.connect(dsn=_pg_dsn())
    try:
        channel = channel_for_run(run_id)
        await conn.execute("SELECT pg_notify($1, $2)", channel, str(event_id))
    finally:
        await conn.close()

    return event_id


async def subscribe(
    run_id: uuid.UUID,
    *,
    last_event_id: int | None = None,
) -> AsyncIterator[Event]:
    """Yield replay events (> last_event_id) then live events."""
    start_after = last_event_id or 0

    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(Event)
                .where(Event.run_id == run_id, Event.id > start_after)
                .order_by(Event.id)
            )
        ).scalars()
        for row in rows:
            yield row

    conn = await asyncpg.connect(dsn=_pg_dsn())
    queue: asyncio.Queue[int] = asyncio.Queue()
    channel = channel_for_run(run_id)

    def _listener(_conn: asyncpg.Connection, _pid: int, _chan: str, payload: str) -> None:
        try:
            queue.put_nowait(int(payload))
        except ValueError:
            return

    await conn.add_listener(channel, _listener)
    try:
        while True:
            event_id = await queue.get()
            async with AsyncSessionLocal() as session:
                event = await session.get(Event, event_id)
                if event is not None and event.run_id == run_id:
                    yield event
    finally:
        await conn.remove_listener(channel, _listener)
        await conn.close()


def encode_sse(event: Event) -> str:
    """SSE framing helper for run events."""
    payload = {
        "id": event.id,
        "run_id": str(event.run_id),
        "ts": event.ts.isoformat(),
        "agent": event.agent,
        "type": event.type,
        "payload": event.payload,
    }
    return f"id: {event.id}\nevent: {event.type}\ndata: {json.dumps(payload)}\n\n"


__all__ = ["channel_for_run", "encode_sse", "publish", "subscribe"]

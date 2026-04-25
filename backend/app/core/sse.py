"""SSE streaming helpers for run events (M5.3)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

from app.core.events import encode_sse, subscribe


async def stream_run_events(
    run_id: uuid.UUID,
    *,
    last_event_id: int | None,
    max_events: int | None = None,
) -> AsyncIterator[str]:
    """Yield SSE-framed event messages for a run."""
    emitted = 0
    async for event in subscribe(run_id, last_event_id=last_event_id):
        yield encode_sse(event)
        emitted += 1
        if max_events is not None and emitted >= max_events:
            break


__all__ = ["stream_run_events"]

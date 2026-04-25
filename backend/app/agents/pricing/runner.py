"""Convenience runner for ad-hoc pricing invocation."""

from __future__ import annotations

from uuid import UUID

from app.agents.pricing.profile import PRICING_PROFILE
from app.workers.run_worker import start_framing


async def run_pricing(run_id: UUID) -> None:
    await start_framing(run_id, profile=PRICING_PROFILE)

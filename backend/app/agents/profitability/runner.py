"""Convenience runner for ad-hoc invocation."""

from __future__ import annotations

from uuid import UUID

from app.agents.profitability.profile import PROFITABILITY_PROFILE
from app.workers.run_worker import start_framing


async def run_profitability(run_id: UUID) -> None:
    await start_framing(run_id, profile=PROFITABILITY_PROFILE)

"""Conditional-edge helpers for the market-entry graph (M6.10).

LangGraph routes by string return values. ``route_after_reviewer``
inspects the gate verdict for ``stage_slug`` plus the run-wide
``cancelled`` flag and returns the next node label.
"""

from __future__ import annotations

from collections.abc import Callable

from app.agents.market_entry.state import RunState

# Configurable in `make_routes`; default mirrors V1 plan §M2.4.
DEFAULT_MAX_STAGE_RETRIES = 2


def make_route_after_reviewer(
    stage_slug: str,
    *,
    next_stage: str,
    redo_stage: str,
    max_attempts: int = DEFAULT_MAX_STAGE_RETRIES + 1,
    cancelled_target: str = "audit",
) -> Callable[[RunState], str]:
    """Return a LangGraph conditional-edge function.

    Decision matrix:
      cancelled      → ``cancelled_target``
      verdict=advance → ``next_stage``
      verdict=reiterate AND attempt<=max_attempts → ``redo_stage``
      otherwise (max retries exhausted)            → ``next_stage``
    """

    def _route(state: RunState) -> str:
        if state.get("cancelled"):
            return cancelled_target
        verdicts = state.get("gate_verdicts") or {}
        v = verdicts.get(stage_slug)
        if v is None or v.get("verdict") == "advance":
            return next_stage
        attempts = (state.get("stage_attempts") or {}).get(stage_slug, 1)
        if attempts > max_attempts:
            return next_stage
        return redo_stage

    return _route


__all__ = ["DEFAULT_MAX_STAGE_RETRIES", "make_route_after_reviewer"]

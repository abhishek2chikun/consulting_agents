"""Typed state contract for the M&A stub graph (M8.1).

V1 only carries `run_id` and `goal` through the single placeholder
node. V2 will extend this with a deal thesis, target list, and
synergy projections — keeping the same `run_id`/`goal` prelude lets
us reuse the worker dispatch and event-emission scaffolding.
"""

from __future__ import annotations

from typing import TypedDict


class MaState(TypedDict, total=False):
    run_id: str
    goal: str


__all__ = ["MaState"]

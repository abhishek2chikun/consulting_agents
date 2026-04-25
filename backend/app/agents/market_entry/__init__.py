"""Market-entry graph package (M5.4 skeleton)."""

from app.agents._engine.registry import PROFILE_REGISTRY, register_profile
from app.agents.market_entry.graph import build_graph, postgres_checkpointer
from app.agents.market_entry.profile import MARKET_ENTRY_PROFILE
from app.agents.market_entry.state import EvidenceRef, FramingBrief, GateVerdict, RunState


def _register_profile_once() -> None:
    existing = PROFILE_REGISTRY.get("market_entry")
    if existing is MARKET_ENTRY_PROFILE:
        return
    if existing is not None:
        raise ValueError("profile 'market_entry' already registered with a different object")
    register_profile(MARKET_ENTRY_PROFILE)


_register_profile_once()

__all__ = [
    "EvidenceRef",
    "FramingBrief",
    "GateVerdict",
    "MARKET_ENTRY_PROFILE",
    "RunState",
    "build_graph",
    "postgres_checkpointer",
]

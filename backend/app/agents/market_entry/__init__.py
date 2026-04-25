"""Market-entry graph package (M5.4 skeleton)."""

from app.agents._engine.registry import PROFILE_REGISTRY, register_profile
from app.agents.market_entry.graph import build_graph, postgres_checkpointer
from app.agents.market_entry.profile import MARKET_ENTRY_PROFILE
from app.agents.market_entry.state import EvidenceRef, FramingBrief, GateVerdict, RunState

if "market_entry" not in PROFILE_REGISTRY:
    register_profile(MARKET_ENTRY_PROFILE)

__all__ = [
    "EvidenceRef",
    "FramingBrief",
    "GateVerdict",
    "MARKET_ENTRY_PROFILE",
    "RunState",
    "build_graph",
    "postgres_checkpointer",
]

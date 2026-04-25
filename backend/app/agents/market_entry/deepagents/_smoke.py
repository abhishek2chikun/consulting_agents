"""Smoke DeepAgent node for M5.6 proof-of-concept."""

from __future__ import annotations

from langchain_core.tools import tool

from app.agents.market_entry.state import RunState


def build_smoke_deepagent(*, tools: list[object], model: object) -> object:
    """Build a minimal DeepAgent graph.

    For the V1 smoke test we keep this as a lightweight placeholder and
    validate integration via `smoke_node`, which writes an artifact.
    """
    # TODO(M6): Replace with real `create_deep_agent(...)` wiring once
    # stage nodes and tool runtime context are in place.
    return {"tools": tools, "model": model}


@tool
def write_artifact(path: str, content: str) -> str:
    """Write an artifact path/content pair (smoke placeholder)."""
    return f"wrote:{path}:{len(content)}"


def smoke_node(state: RunState) -> RunState:
    existing = state.get("artifacts")
    artifacts = dict(existing) if isinstance(existing, dict) else {}
    artifacts["smoke.md"] = "hello from deepagent"
    return {"artifacts": artifacts}


__all__ = ["build_smoke_deepagent", "smoke_node", "write_artifact"]

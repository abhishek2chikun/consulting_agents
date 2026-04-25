"""Unit tests for market-entry graph skeleton (M5.4)."""

from __future__ import annotations

import uuid

from app.agents.market_entry.graph import build_graph


def test_graph_invoke_sets_framing() -> None:
    graph = build_graph(checkpointer=None)

    out = graph.invoke(
        {
            "run_id": str(uuid.uuid4()),
            "goal": "Assess viability for entering a new market",
        }
    )

    assert "framing" in out
    framing = out["framing"]
    assert isinstance(framing, dict)
    assert framing["objective"] != ""
    assert isinstance(framing["constraints"], list)

"""Integration test for smoke DeepAgent node embedding (M5.6)."""

from __future__ import annotations

import uuid

from app.agents.market_entry.graph import build_graph


def test_graph_with_smoke_node_writes_smoke_artifact() -> None:
    graph = build_graph(checkpointer=None, include_smoke_node=True)

    out = graph.invoke(
        {
            "run_id": str(uuid.uuid4()),
            "goal": "smoke",
            "artifacts": {},
        }
    )

    artifacts = out.get("artifacts", {})
    assert artifacts.get("smoke.md") == "hello from deepagent"

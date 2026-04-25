"""M9.1: build_consulting_graph constructs N-stage pipeline from profile."""

from unittest.mock import Mock

from app.agents._engine.graph import build_consulting_graph
from app.agents.market_entry.profile import MARKET_ENTRY_PROFILE


def test_market_entry_graph_compiles() -> None:
    factory = Mock(return_value=Mock())
    graph = build_consulting_graph(
        MARKET_ENTRY_PROFILE,
        model_factory=factory,
        tools_factory=lambda: [],
    )
    nodes = set(graph.get_graph().nodes.keys())
    expected = {
        "framing",
        "stage1_foundation",
        "reviewer_stage1_foundation",
        "stage2_competitive",
        "reviewer_stage2_competitive",
        "stage3_risk",
        "reviewer_stage3_risk",
        "synthesis",
        "audit",
    }
    assert expected.issubset(nodes)

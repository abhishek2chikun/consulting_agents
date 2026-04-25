"""Market-entry LangGraph wiring (M5.4 skeleton + M6.10 full pipeline)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph

from app.agents._engine.edges import DEFAULT_MAX_STAGE_RETRIES
from app.agents._engine.graph import ModelFactory, ToolsFactory, build_consulting_graph
from app.agents._engine.state import FramingBrief, RunState
from app.agents.market_entry.deepagents._smoke import smoke_node
from app.agents.market_entry.profile import MARKET_ENTRY_PROFILE
from app.core.config import get_settings


def framing_stub(state: RunState) -> RunState:
    goal = state.get("goal", "Define consulting objective")
    framing: FramingBrief = {
        "objective": goal,
        "target_market": "unspecified",
        "constraints": [],
        "questionnaire_answers": {},
    }
    return {"framing": framing}


def done(state: RunState) -> RunState:
    return state


def build_graph(
    *,
    checkpointer: PostgresSaver | None = None,
    include_smoke_node: bool = False,
) -> Any:
    """Compile and return the minimal framing->done skeleton (M5.4).

    Kept for back-compat with the M5.6 smoke-node integration test.
    The full pipeline is in :func:`build_full_graph`.
    """
    graph = StateGraph(RunState)
    graph.add_node("framing_stub", framing_stub)
    graph.add_node("done", done)
    if include_smoke_node:
        graph.add_node("smoke_deepagent", smoke_node)
    graph.add_edge(START, "framing_stub")
    if include_smoke_node:
        graph.add_edge("framing_stub", "smoke_deepagent")
        graph.add_edge("smoke_deepagent", "done")
    else:
        graph.add_edge("framing_stub", "done")
    graph.add_edge("done", END)
    return graph.compile(checkpointer=checkpointer)


def build_full_graph(
    *,
    model_factory: ModelFactory,
    tools_factory: ToolsFactory | None = None,
    checkpointer: PostgresSaver | None = None,
    max_stage_retries: int = DEFAULT_MAX_STAGE_RETRIES,
    include_framing: bool = True,
) -> Any:
    """Compile the full market-entry pipeline."""
    return build_consulting_graph(
        MARKET_ENTRY_PROFILE,
        model_factory=model_factory,
        tools_factory=tools_factory,
        checkpointer=checkpointer,
        max_stage_retries=max_stage_retries,
        include_framing=include_framing,
    )


def postgres_checkpointer() -> Iterator[PostgresSaver]:
    """Context-managed Postgres checkpointer for runtime wiring."""
    dsn = get_settings().database_url.replace("postgresql+asyncpg://", "postgresql://")
    with PostgresSaver.from_conn_string(dsn) as saver:
        saver.setup()
        yield saver


__all__ = [
    "ModelFactory",
    "ToolsFactory",
    "build_full_graph",
    "build_graph",
    "postgres_checkpointer",
]

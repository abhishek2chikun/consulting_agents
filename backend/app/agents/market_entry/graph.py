"""Minimal market-entry graph skeleton (M5.4)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph

from app.agents.market_entry.deepagents._smoke import smoke_node
from app.agents.market_entry.state import FramingBrief, RunState
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
    """Compile and return the minimal framing->done graph."""
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


def postgres_checkpointer() -> Iterator[PostgresSaver]:
    """Context-managed Postgres checkpointer for runtime wiring."""
    dsn = get_settings().database_url.replace("postgresql+asyncpg://", "postgresql://")
    with PostgresSaver.from_conn_string(dsn) as saver:
        saver.setup()
        yield saver


__all__ = ["build_graph", "postgres_checkpointer"]

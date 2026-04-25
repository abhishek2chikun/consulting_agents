"""Market-entry LangGraph wiring (M5.4 skeleton + M6.10 full pipeline)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph

from app.agents.market_entry.deepagents._smoke import smoke_node
from app.agents.market_entry.edges import (
    DEFAULT_MAX_STAGE_RETRIES,
    make_route_after_reviewer,
)
from app.agents.market_entry.nodes.audit import build_audit_node
from app.agents.market_entry.nodes.framing import build_framing_node
from app.agents.market_entry.nodes.reviewer import make_reviewer_node
from app.agents.market_entry.nodes.stage import make_stage_node
from app.agents.market_entry.nodes.synthesis import build_synthesis_node
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


# ---------------------------------------------------------------------------
# Full pipeline (M6.10)
# ---------------------------------------------------------------------------

ModelFactory = Callable[[str], object]
"""(role) -> chat model. Roles: framing|research|reviewer|synthesis|audit."""

ToolsFactory = Callable[[], list[object]]


def build_full_graph(
    *,
    model_factory: ModelFactory,
    tools_factory: ToolsFactory | None = None,
    checkpointer: PostgresSaver | None = None,
    max_stage_retries: int = DEFAULT_MAX_STAGE_RETRIES,
    include_framing: bool = True,
) -> Any:
    """Compile the full market-entry pipeline.

    Pipeline:
      START → framing → stage1 → reviewer1 → (stage1 | stage2)
                                ↓ cancelled
                                audit
            stage2 → reviewer2 → (stage2 | stage3)
            stage3 → reviewer3 → (stage3 | synthesis)
            synthesis → audit → END

    ``include_framing`` lets the run worker skip framing on the second
    leg of the run (after the human submits answers we resume from
    ``stage1_foundation``).
    """
    tools = tools_factory() if tools_factory is not None else []
    max_attempts = max_stage_retries + 1

    framing_model = model_factory("framing")
    research_model = model_factory("research")
    reviewer_model = model_factory("reviewer")
    synthesis_model = model_factory("synthesis")
    audit_model = model_factory("audit")

    graph = StateGraph(RunState)
    graph.add_node("framing", build_framing_node(model=framing_model))  # type: ignore[arg-type]

    graph.add_node(
        "stage1_foundation",
        make_stage_node("stage1_foundation", model=research_model, tools=tools),  # type: ignore[arg-type]
    )
    graph.add_node(
        "reviewer_stage1",
        make_reviewer_node("stage1_foundation", model=reviewer_model),  # type: ignore[arg-type]
    )

    graph.add_node(
        "stage2_competitive",
        make_stage_node("stage2_competitive", model=research_model, tools=tools),  # type: ignore[arg-type]
    )
    graph.add_node(
        "reviewer_stage2",
        make_reviewer_node("stage2_competitive", model=reviewer_model),  # type: ignore[arg-type]
    )

    graph.add_node(
        "stage3_risk",
        make_stage_node("stage3_risk", model=research_model, tools=tools),  # type: ignore[arg-type]
    )
    graph.add_node(
        "reviewer_stage3",
        make_reviewer_node("stage3_risk", model=reviewer_model),  # type: ignore[arg-type]
    )

    graph.add_node("synthesis", build_synthesis_node(model=synthesis_model))  # type: ignore[arg-type]
    graph.add_node("audit", build_audit_node(model=audit_model))  # type: ignore[arg-type]

    if include_framing:
        graph.add_edge(START, "framing")
        # Framing node persists the questionnaire and waits for answers
        # via the run worker (the worker resumes the graph at
        # `stage1_foundation` after `submit_answers`). For tests we link
        # framing directly to stage1 so a single `invoke()` flows
        # through the whole pipeline; the run worker uses
        # `include_framing=False` for its second leg.
        graph.add_edge("framing", "stage1_foundation")
    else:
        graph.add_edge(START, "stage1_foundation")

    graph.add_edge("stage1_foundation", "reviewer_stage1")
    graph.add_conditional_edges(
        "reviewer_stage1",
        make_route_after_reviewer(
            "stage1_foundation",
            next_stage="stage2_competitive",
            redo_stage="stage1_foundation",
            max_attempts=max_attempts,
        ),
        {
            "stage1_foundation": "stage1_foundation",
            "stage2_competitive": "stage2_competitive",
            "audit": "audit",
        },
    )

    graph.add_edge("stage2_competitive", "reviewer_stage2")
    graph.add_conditional_edges(
        "reviewer_stage2",
        make_route_after_reviewer(
            "stage2_competitive",
            next_stage="stage3_risk",
            redo_stage="stage2_competitive",
            max_attempts=max_attempts,
        ),
        {
            "stage2_competitive": "stage2_competitive",
            "stage3_risk": "stage3_risk",
            "audit": "audit",
        },
    )

    graph.add_edge("stage3_risk", "reviewer_stage3")
    graph.add_conditional_edges(
        "reviewer_stage3",
        make_route_after_reviewer(
            "stage3_risk",
            next_stage="synthesis",
            redo_stage="stage3_risk",
            max_attempts=max_attempts,
        ),
        {
            "stage3_risk": "stage3_risk",
            "synthesis": "synthesis",
            "audit": "audit",
        },
    )

    graph.add_edge("synthesis", "audit")
    graph.add_edge("audit", END)

    return graph.compile(checkpointer=checkpointer)


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

"""Profile-driven LangGraph wiring for consulting pipelines."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from langgraph.graph import END, START, StateGraph

from app.agents._engine.edges import DEFAULT_MAX_STAGE_RETRIES, make_route_after_reviewer
from app.agents._engine.nodes.audit import build_audit_node
from app.agents._engine.nodes.framing import build_framing_node
from app.agents._engine.nodes.reviewer import make_reviewer_node
from app.agents._engine.nodes.stage import make_stage_node
from app.agents._engine.nodes.synthesis import build_synthesis_node
from app.agents._engine.profile import ConsultingProfile
from app.agents._engine.state import RunState

ModelFactory = Callable[[str], object]
"""(role) -> chat model. Roles: framing|research|reviewer|synthesis|audit."""

ToolsFactory = Callable[[], list[object]]


def build_consulting_graph(
    profile: ConsultingProfile,
    *,
    model_factory: ModelFactory,
    tools_factory: ToolsFactory | None = None,
    checkpointer: Any | None = None,
    max_stage_retries: int = DEFAULT_MAX_STAGE_RETRIES,
    include_framing: bool = True,
) -> Any:
    """Compile the N-stage consulting pipeline for ``profile``."""
    if not profile.stages:
        raise ValueError(f"profile {profile.slug} must define at least one stage")

    tools = tools_factory() if tools_factory is not None else []
    framing_model = model_factory("framing")
    research_model = model_factory("research")
    reviewer_model = model_factory("reviewer")
    synthesis_model = model_factory("synthesis")
    audit_model = model_factory("audit")

    graph = StateGraph(RunState)
    graph.add_node("framing", cast(Any, build_framing_node(model=framing_model, profile=profile)))

    for stage in profile.stages:
        reviewer_node = f"reviewer_{stage.node_name}"
        graph.add_node(
            stage.node_name,
            cast(
                Any,
                make_stage_node(stage.slug, model=research_model, tools=tools, profile=profile),
            ),
        )
        graph.add_node(
            reviewer_node,
            cast(Any, make_reviewer_node(stage.slug, model=reviewer_model, profile=profile)),
        )

    graph.add_node(
        "synthesis",
        cast(Any, build_synthesis_node(model=synthesis_model, profile=profile)),
    )
    graph.add_node("audit", cast(Any, build_audit_node(model=audit_model, profile=profile)))

    first_stage = profile.stages[0].node_name
    if include_framing:
        graph.add_edge(START, "framing")
        graph.add_edge("framing", first_stage)
    else:
        graph.add_edge(START, first_stage)

    for stage in profile.stages:
        reviewer_node = f"reviewer_{stage.node_name}"
        stage_max_retries = (
            stage.max_retries if stage.max_retries is not None else max_stage_retries
        )
        graph.add_edge(stage.node_name, reviewer_node)
        graph.add_conditional_edges(
            reviewer_node,
            make_route_after_reviewer(
                stage.slug,
                next_stage=stage.next_stage_node,
                redo_stage=stage.node_name,
                max_attempts=stage_max_retries + 1,
            ),
            {
                stage.node_name: stage.node_name,
                stage.next_stage_node: stage.next_stage_node,
                "audit": "audit",
            },
        )

    graph.add_edge("synthesis", "audit")
    graph.add_edge("audit", END)

    return graph.compile(checkpointer=checkpointer)


__all__ = ["ModelFactory", "ToolsFactory", "build_consulting_graph"]

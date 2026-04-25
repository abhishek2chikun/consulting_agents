"""Single-node "graph" for the M&A V2 stub (M8.1).

This is structured as a `langgraph.StateGraph` with one node so that
the V2 expansion has an obvious extension point: just add nodes and
edges, keep `run_id`/`goal` flowing through `MaState`. For V1 the
graph compiles to a degenerate `START → placeholder → END` flow.

The placeholder node reads `prompts/placeholder.md`, substitutes the
run goal, writes it as `final_report.md`, transitions
`Run.status -> completed`, and emits the matching `artifact_update`
+ `run_completed` SSE events.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from importlib import resources

from langgraph.graph import END, START, StateGraph
from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.core.events import publish
from app.models import Artifact, Run, RunStatus

from .state import MaState

REPORT_PATH = "final_report.md"
_PLACEHOLDER_TEMPLATE = (
    resources.files("app.agents.ma.prompts").joinpath("placeholder.md").read_text()
)


def _render_placeholder(goal: str) -> str:
    return _PLACEHOLDER_TEMPLATE.replace("{goal}", goal or "(no goal provided)")


def build_placeholder_node() -> Callable[[MaState], Awaitable[MaState]]:
    async def placeholder_node(state: MaState) -> MaState:
        run_uuid = uuid.UUID(state["run_id"])
        goal = state.get("goal", "")
        body = _render_placeholder(goal)

        async with AsyncSessionLocal() as session:
            existing = (
                await session.execute(
                    select(Artifact).where(
                        Artifact.run_id == run_uuid,
                        Artifact.path == REPORT_PATH,
                    )
                )
            ).scalar_one_or_none()
            if existing is None:
                session.add(
                    Artifact(
                        run_id=run_uuid,
                        path=REPORT_PATH,
                        kind="markdown",
                        content=body,
                    )
                )
            else:
                existing.kind = "markdown"
                existing.content = body

            run = await session.get(Run, run_uuid)
            if run is not None and run.status not in (
                RunStatus.cancelled,
                RunStatus.failed,
            ):
                run.status = RunStatus.completed
            await session.commit()

        await publish(
            run_uuid,
            "artifact_update",
            {"path": REPORT_PATH},
            agent="ma.placeholder",
        )
        await publish(run_uuid, "run_completed", {}, agent="ma.placeholder")
        return state

    return placeholder_node


def build_graph() -> object:
    """Compile the one-node M&A stub graph.

    Returned object exposes `astream(initial_state)` like the
    market-entry graph, so the worker can drive both with the same
    cancel-aware loop.
    """
    g: StateGraph[MaState] = StateGraph(MaState)
    g.add_node("placeholder", build_placeholder_node())  # type: ignore[call-overload]
    g.add_edge(START, "placeholder")
    g.add_edge("placeholder", END)
    return g.compile()


__all__ = ["REPORT_PATH", "build_graph", "build_placeholder_node"]

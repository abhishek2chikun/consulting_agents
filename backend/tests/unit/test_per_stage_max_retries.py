"""V1.6: per-stage retry overrides are wired into reviewer routes."""

from __future__ import annotations

from collections.abc import Callable
from unittest.mock import Mock

from app.agents._engine import graph as engine_graph
from app.agents._engine.profile import ConsultingProfile, ProfileStage
from app.agents._engine.state import RunState


def make_profile(*, max_retries: int | None) -> ConsultingProfile:
    return ConsultingProfile(
        slug="retry_test",
        display_name="Retry Test",
        prompts_package="app.agents.market_entry.prompts",
        framing_prompt="framing.md",
        stages=(
            ProfileStage(
                slug="stage1_foundation",
                node_name="stage1_foundation",
                next_stage_node="synthesis",
                prompt_file="stage1_foundation.md",
                max_retries=max_retries,
            ),
        ),
        reviewer_prompt_package="app.agents.market_entry.prompts",
        reviewer_prompt="reviewer.md",
        synthesis_prompt="synthesis.md",
        audit_prompt="audit.md",
    )


def capture_stage_route(
    monkeypatch,
    *,
    stage_max_retries: int | None,
    global_max_retries: int,
) -> Callable[[RunState], str]:
    routes: dict[str, Callable[[RunState], str]] = {}
    original = engine_graph.make_route_after_reviewer

    def capturing_route(stage_slug: str, **kwargs):
        route = original(stage_slug, **kwargs)
        routes[stage_slug] = route
        return route

    monkeypatch.setattr(engine_graph, "make_route_after_reviewer", capturing_route)
    engine_graph.build_consulting_graph(
        make_profile(max_retries=stage_max_retries),
        model_factory=Mock(return_value=Mock()),
        tools_factory=lambda: [],
        max_stage_retries=global_max_retries,
    )
    return routes["stage1_foundation"]


def reiterate_state(*, attempts: int) -> RunState:
    return {
        "cancelled": False,
        "gate_verdicts": {"stage1_foundation": {"verdict": "reiterate"}},
        "stage_attempts": {"stage1_foundation": attempts},
    }


def test_stage_max_retries_override_controls_reviewer_route(monkeypatch) -> None:
    route = capture_stage_route(
        monkeypatch,
        stage_max_retries=5,
        global_max_retries=2,
    )

    assert route(reiterate_state(attempts=6)) == "stage1_foundation"
    assert route(reiterate_state(attempts=7)) == "synthesis"


def test_stage_max_retries_none_falls_back_to_global_route_limit(monkeypatch) -> None:
    route = capture_stage_route(
        monkeypatch,
        stage_max_retries=None,
        global_max_retries=2,
    )

    assert route(reiterate_state(attempts=3)) == "stage1_foundation"
    assert route(reiterate_state(attempts=4)) == "synthesis"

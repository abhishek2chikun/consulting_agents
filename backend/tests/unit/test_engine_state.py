"""M9.1: shared engine state lives in _engine and re-exports through market_entry."""

from app.agents._engine.edges import (
    DEFAULT_MAX_STAGE_RETRIES,
    make_route_after_reviewer,
)
from app.agents._engine.state import FramingBrief, RunState
from app.agents.market_entry.edges import make_route_after_reviewer as me_route
from app.agents.market_entry.state import RunState as MERunState


def test_runstate_is_shared() -> None:
    assert MERunState is RunState


def test_route_is_shared() -> None:
    assert me_route is make_route_after_reviewer


def test_framing_brief_keys() -> None:
    fb: FramingBrief = {
        "objective": "x",
        "target_market": "y",
        "constraints": [],
        "questionnaire_answers": {},
    }
    assert fb["objective"] == "x"


def test_default_retries_is_int() -> None:
    assert isinstance(DEFAULT_MAX_STAGE_RETRIES, int)

"""M9.1: MARKET_ENTRY_PROFILE is registered and loads prompts."""

from app.agents._engine.registry import PROFILE_REGISTRY
from app.agents.market_entry import MARKET_ENTRY_PROFILE


def test_profile_registered() -> None:
    assert PROFILE_REGISTRY.get("market_entry") is MARKET_ENTRY_PROFILE


def test_profile_has_three_stages_today() -> None:
    # Will become 5 in Task 7 (stage expansion).
    assert len(MARKET_ENTRY_PROFILE.stages) == 3


def test_profile_loads_framing_prompt() -> None:
    text = MARKET_ENTRY_PROFILE.load_prompt("framing")
    assert len(text) > 100

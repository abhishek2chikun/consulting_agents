"""M9.1: MARKET_ENTRY_PROFILE is registered and loads prompts."""

import pytest

from app.agents._engine.profile import ConsultingProfile
from app.agents._engine.registry import PROFILE_REGISTRY
from app.agents.market_entry import MARKET_ENTRY_PROFILE, _register_profile_once


def test_profile_registered() -> None:
    assert PROFILE_REGISTRY.get("market_entry") is MARKET_ENTRY_PROFILE


def test_profile_has_five_stages() -> None:
    assert [
        (stage.slug, stage.node_name, stage.next_stage_node)
        for stage in MARKET_ENTRY_PROFILE.stages
    ] == [
        ("stage1_foundation", "stage1_foundation", "stage2_competitive"),
        ("stage2_competitive", "stage2_competitive", "stage3_risk"),
        ("stage3_risk", "stage3_risk", "stage4_demand"),
        ("stage4_demand", "stage4_demand", "stage5_strategy"),
        ("stage5_strategy", "stage5_strategy", "synthesis"),
    ]


def test_profile_loads_framing_prompt() -> None:
    text = MARKET_ENTRY_PROFILE.load_prompt("framing")
    assert len(text) > 100


def test_register_profile_once_rejects_mismatched_registry_entry() -> None:
    original = PROFILE_REGISTRY.get("market_entry")
    other_profile = ConsultingProfile(
        slug="market_entry",
        display_name="Other Market Entry",
        prompts_package="app.agents.market_entry.prompts",
        framing_prompt="framing.md",
        stages=(),
        reviewer_prompt_package="app.agents.market_entry.prompts",
        reviewer_prompt="reviewer.md",
        synthesis_prompt="synthesis.md",
        audit_prompt="audit.md",
    )

    try:
        PROFILE_REGISTRY["market_entry"] = other_profile
        with pytest.raises(
            ValueError,
            match="profile 'market_entry' already registered with a different object",
        ):
            _register_profile_once()
    finally:
        if original is None:
            PROFILE_REGISTRY.pop("market_entry", None)
        else:
            PROFILE_REGISTRY["market_entry"] = original

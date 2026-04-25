"""M9.1: ConsultingProfile loads prompts; registry stores by slug."""

from __future__ import annotations

import pytest

from app.agents._engine.profile import ConsultingProfile, ProfileStage
from app.agents._engine.registry import PROFILE_REGISTRY, get_profile, register_profile


def make_profile(slug: str = "test_type") -> ConsultingProfile:
    return ConsultingProfile(
        slug=slug,
        display_name="Test Type",
        prompts_package="app.agents.market_entry.prompts",
        framing_prompt="framing.md",
        stages=(
            ProfileStage(
                slug="stage1_foundation",
                node_name="stage1_foundation",
                next_stage_node="audit",
                prompt_file="stage1_foundation.md",
            ),
        ),
        reviewer_prompt_package="app.agents.market_entry.prompts",
        reviewer_prompt="reviewer.md",
        synthesis_prompt="synthesis.md",
        audit_prompt="audit.md",
    )


def test_load_prompt_returns_str() -> None:
    p = make_profile()
    assert "objective" in p.load_prompt("framing").lower() or len(p.load_prompt("framing")) > 0


def test_register_and_get() -> None:
    p = make_profile("regtest_a")
    register_profile(p)
    try:
        assert get_profile("regtest_a") is p
        assert "regtest_a" in PROFILE_REGISTRY
    finally:
        PROFILE_REGISTRY.pop("regtest_a", None)


def test_duplicate_register_raises() -> None:
    p = make_profile("regtest_b")
    register_profile(p)
    try:
        with pytest.raises(ValueError, match="already registered"):
            register_profile(make_profile("regtest_b"))
    finally:
        PROFILE_REGISTRY.pop("regtest_b", None)


def test_get_unknown_returns_none() -> None:
    assert get_profile("does_not_exist") is None


def test_validation_at_construction() -> None:
    """A profile pointing at a missing prompt file must fail fast."""
    with pytest.raises(FileNotFoundError):
        ConsultingProfile(
            slug="bad",
            display_name="Bad",
            prompts_package="app.agents.market_entry.prompts",
            framing_prompt="does_not_exist.md",
            stages=(),
            reviewer_prompt_package="app.agents.market_entry.prompts",
            reviewer_prompt="reviewer.md",
            synthesis_prompt="synthesis.md",
            audit_prompt="audit.md",
        ).validate()

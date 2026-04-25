"""Task 13: pricing profile registered and prompts load."""

import pytest

import app.agents.pricing  # noqa: F401  # import triggers registration
from app.agents._engine.profile import ConsultingProfile
from app.agents._engine.registry import PROFILE_REGISTRY
from app.agents.pricing import PRICING_PROFILE, _register_profile_once

STAGE_ARTIFACTS = {
    "stage1_value": "stage1_value.md",
    "stage2_segments": "stage2_segments.md",
    "stage3_competitive": "stage3_competitive.md",
    "stage4_models": "stage4_models.md",
    "stage5_rollout": "stage5_rollout.md",
}


def test_registered() -> None:
    assert PROFILE_REGISTRY.get("pricing") is PRICING_PROFILE


def test_five_stages() -> None:
    p = PROFILE_REGISTRY["pricing"]
    assert len(p.stages) == 5
    assert [s.slug for s in p.stages] == [
        "stage1_value",
        "stage2_segments",
        "stage3_competitive",
        "stage4_models",
        "stage5_rollout",
    ]
    assert [s.next_stage_node for s in p.stages] == [
        "stage2_segments",
        "stage3_competitive",
        "stage4_models",
        "stage5_rollout",
        "synthesis",
    ]


def test_all_prompts_load() -> None:
    p = PROFILE_REGISTRY["pricing"]
    for role in ("framing", "synthesis", "audit", "reviewer"):
        assert len(p.load_prompt(role)) > 50
    for stage in p.stages:
        assert len(p.load_prompt(stage.slug)) > 50


def test_register_profile_once_rejects_mismatched_registry_entry() -> None:
    original = PROFILE_REGISTRY.get("pricing")
    other_profile = ConsultingProfile(
        slug="pricing",
        display_name="Other Pricing",
        prompts_package="app.agents.pricing.prompts",
        framing_prompt="framing.md",
        stages=(),
        reviewer_prompt_package="app.agents.market_entry.prompts",
        reviewer_prompt="reviewer.md",
        synthesis_prompt="synthesis.md",
        audit_prompt="audit.md",
    )

    try:
        PROFILE_REGISTRY["pricing"] = other_profile
        with pytest.raises(
            ValueError,
            match="profile 'pricing' already registered with a different object",
        ):
            _register_profile_once()
    finally:
        if original is None:
            PROFILE_REGISTRY.pop("pricing", None)
        else:
            PROFILE_REGISTRY["pricing"] = original


def test_stage_prompts_describe_stage_output_contract() -> None:
    for stage in PRICING_PROFILE.stages:
        text = PRICING_PROFILE.load_prompt(stage.slug)

        assert "StageOutput" in text
        assert "artifacts" in text
        assert "evidence" in text
        assert STAGE_ARTIFACTS[stage.slug] in text
        assert "[^src_id]" in text


def test_stage_prompts_exclude_stale_citation_and_output_patterns() -> None:
    stale_patterns = ("[1]", "[2]", "final_report.md", "### References")

    for stage in PRICING_PROFILE.stages:
        text = PRICING_PROFILE.load_prompt(stage.slug)

        for pattern in stale_patterns:
            assert pattern not in text


def test_synthesis_prompt_describes_pricing_report_and_sources() -> None:
    text = PRICING_PROFILE.load_prompt("synthesis")

    for section in (
        "## Executive Summary",
        "## Engagement Context",
        "## Value & WTP",
        "## Segment Pricing",
        "## Competitive Price Position",
        "## Pricing Model Options",
        "## Pricing Recommendation & Rollout",
        "## KPI/Experiment Plan",
    ):
        assert section in text
    assert "final_report.md" in text
    assert "Do NOT" in text
    assert "sources section" in text.lower()


def test_audit_prompt_matches_runtime_artifact_path() -> None:
    text = PRICING_PROFILE.load_prompt("audit")

    assert "audit.md" in text
    assert "audit_report.md" not in text

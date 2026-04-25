"""M9.2: profitability profile registered and prompts load."""

import pytest

import app.agents.profitability  # noqa: F401  # import triggers registration
from app.agents._engine.profile import ConsultingProfile
from app.agents._engine.registry import PROFILE_REGISTRY
from app.agents.profitability import PROFITABILITY_PROFILE, _register_profile_once

STAGE_ARTIFACTS = {
    "stage1_revenue": "stage1_revenue.md",
    "stage2_cost": "stage2_cost.md",
    "stage3_margin": "stage3_margin.md",
    "stage4_competitor": "stage4_competitor.md",
    "stage5_levers": "stage5_levers.md",
}


def test_registered() -> None:
    assert PROFILE_REGISTRY.get("profitability") is PROFITABILITY_PROFILE


def test_five_stages() -> None:
    p = PROFILE_REGISTRY["profitability"]
    assert len(p.stages) == 5
    assert [s.slug for s in p.stages] == [
        "stage1_revenue",
        "stage2_cost",
        "stage3_margin",
        "stage4_competitor",
        "stage5_levers",
    ]
    assert [s.next_stage_node for s in p.stages] == [
        "stage2_cost",
        "stage3_margin",
        "stage4_competitor",
        "stage5_levers",
        "synthesis",
    ]


def test_all_prompts_load() -> None:
    p = PROFILE_REGISTRY["profitability"]
    for role in ("framing", "synthesis", "audit", "reviewer"):
        assert len(p.load_prompt(role)) > 50
    for stage in p.stages:
        assert len(p.load_prompt(stage.slug)) > 50


def test_register_profile_once_rejects_mismatched_registry_entry() -> None:
    original = PROFILE_REGISTRY.get("profitability")
    other_profile = ConsultingProfile(
        slug="profitability",
        display_name="Other Profitability",
        prompts_package="app.agents.profitability.prompts",
        framing_prompt="framing.md",
        stages=(),
        reviewer_prompt_package="app.agents.market_entry.prompts",
        reviewer_prompt="reviewer.md",
        synthesis_prompt="synthesis.md",
        audit_prompt="audit.md",
    )

    try:
        PROFILE_REGISTRY["profitability"] = other_profile
        with pytest.raises(
            ValueError,
            match="profile 'profitability' already registered with a different object",
        ):
            _register_profile_once()
    finally:
        if original is None:
            PROFILE_REGISTRY.pop("profitability", None)
        else:
            PROFILE_REGISTRY["profitability"] = original


def test_stage_prompts_describe_stage_output_contract() -> None:
    for stage in PROFITABILITY_PROFILE.stages:
        text = PROFITABILITY_PROFILE.load_prompt(stage.slug)

        assert "StageOutput" in text
        assert "artifacts" in text
        assert "evidence" in text
        assert STAGE_ARTIFACTS[stage.slug] in text
        assert "[^src_id]" in text


def test_stage_prompts_exclude_stale_citation_and_output_patterns() -> None:
    stale_patterns = ("[1]", "[2]", "final_report.md", "### References")

    for stage in PROFITABILITY_PROFILE.stages:
        text = PROFITABILITY_PROFILE.load_prompt(stage.slug)

        for pattern in stale_patterns:
            assert pattern not in text


def test_synthesis_prompt_describes_profitability_report_and_sources() -> None:
    text = PROFITABILITY_PROFILE.load_prompt("synthesis")

    for section in (
        "## Executive Summary",
        "## Engagement Context",
        "## Revenue Analysis",
        "## Cost Structure",
        "## Margin Analysis",
        "## Competitive Margin Benchmarking",
        "## Profit Improvement Levers",
        "## KPI Dashboard",
    ):
        assert section in text
    assert "final_report.md" in text
    assert "Do NOT" in text
    assert "sources section" in text.lower()


def test_audit_prompt_matches_runtime_artifact_path() -> None:
    text = PROFITABILITY_PROFILE.load_prompt("audit")

    assert "audit.md" in text
    assert "audit_report.md" not in text

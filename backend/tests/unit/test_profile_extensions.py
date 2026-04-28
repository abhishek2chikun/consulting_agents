"""Task 6: profile schema supports skills and worker specs."""

from __future__ import annotations

import pytest

from app.agents._engine.profile import ConsultingProfile, ProfileStage, WorkerSpec
from app.agents.market_entry import MARKET_ENTRY_PROFILE
from app.agents.pricing import PRICING_PROFILE
from app.agents.profitability import PROFITABILITY_PROFILE


def make_profile(
    *,
    stages: tuple[ProfileStage, ...] | None = None,
    framing_skills: tuple[str, ...] = (),
    synthesis_skills: tuple[str, ...] = (),
    audit_skills: tuple[str, ...] = (),
    reviewer_skills_per_stage: dict[str, tuple[str, ...]] | None = None,
    reviewer_prompt_for_stage: dict[str, str] | None = None,
) -> ConsultingProfile:
    return ConsultingProfile(
        slug="test_profile",
        display_name="Test Profile",
        prompts_package="app.agents.market_entry.prompts",
        framing_prompt="framing.md",
        stages=(
            ProfileStage(
                slug="stage1_foundation",
                node_name="stage1_foundation",
                next_stage_node="synthesis",
                prompt_file="stage1_foundation.md",
            ),
        )
        if stages is None
        else stages,
        reviewer_prompt_package="app.agents.market_entry.prompts",
        reviewer_prompt="reviewer.md",
        synthesis_prompt="synthesis.md",
        audit_prompt="audit.md",
        framing_skills=framing_skills,
        synthesis_skills=synthesis_skills,
        audit_skills=audit_skills,
        reviewer_skills_per_stage={}
        if reviewer_skills_per_stage is None
        else reviewer_skills_per_stage,
        reviewer_prompt_for_stage={}
        if reviewer_prompt_for_stage is None
        else reviewer_prompt_for_stage,
    )


def test_new_profile_stage_and_consulting_profile_fields_default_empty_or_none() -> None:
    stage = ProfileStage(
        slug="stage1_foundation",
        node_name="stage1_foundation",
        next_stage_node="synthesis",
        prompt_file="stage1_foundation.md",
    )
    profile = make_profile()

    assert stage.required_skills == ()
    assert stage.workers == ()
    assert stage.max_retries is None
    assert profile.framing_skills == ()
    assert profile.synthesis_skills == ()
    assert profile.audit_skills == ()
    assert profile.reviewer_skills_per_stage == {}
    assert profile.reviewer_prompt_for_stage == {}


def test_load_worker_prompt_loads_existing_worker_prompt() -> None:
    profile = make_profile(
        stages=(
            ProfileStage(
                slug="stage1_foundation",
                node_name="stage1_foundation",
                next_stage_node="synthesis",
                prompt_file="stage1_foundation.md",
                workers=(
                    WorkerSpec(
                        slug="market_sizing",
                        prompt_file="stage1/market_sizing.md",
                    ),
                ),
            ),
        )
    )

    assert len(profile.load_worker_prompt("stage1_foundation", "market_sizing")) > 50


def test_load_worker_prompt_missing_stage_raises_key_error_with_stage_slug() -> None:
    profile = make_profile()

    with pytest.raises(KeyError, match="missing_stage"):
        profile.load_worker_prompt("missing_stage", "market_sizing")


def test_load_worker_prompt_missing_worker_raises_key_error_with_worker_slug() -> None:
    profile = make_profile()

    with pytest.raises(KeyError, match="missing_worker"):
        profile.load_worker_prompt("stage1_foundation", "missing_worker")


def test_validate_reads_every_referenced_skill() -> None:
    profile = make_profile(framing_skills=("does-not-exist",))

    with pytest.raises(FileNotFoundError, match="does-not-exist"):
        profile.validate()


def test_validate_reads_per_stage_reviewer_prompt() -> None:
    profile = make_profile(reviewer_prompt_for_stage={"stage1_foundation": "does_not_exist.md"})

    with pytest.raises(FileNotFoundError):
        profile.validate()


def test_validate_rejects_unknown_reviewer_prompt_for_stage_key() -> None:
    profile = make_profile(reviewer_prompt_for_stage={"unknown_stage": "reviewer.md"})

    with pytest.raises(ValueError, match="unknown_stage"):
        profile.validate()


def test_validate_rejects_unknown_reviewer_skills_per_stage_key() -> None:
    profile = make_profile(reviewer_skills_per_stage={"unknown_stage": ()})

    with pytest.raises(ValueError, match="unknown_stage"):
        profile.validate()


def test_validate_reads_every_worker_prompt_and_rejects_missing_worker_prompt() -> None:
    profile = make_profile(
        stages=(
            ProfileStage(
                slug="stage1_foundation",
                node_name="stage1_foundation",
                next_stage_node="synthesis",
                prompt_file="stage1_foundation.md",
                workers=(
                    WorkerSpec(
                        slug="market_sizing",
                        prompt_file="stage1/does_not_exist.md",
                    ),
                ),
            ),
        )
    )

    with pytest.raises(FileNotFoundError):
        profile.validate()


def test_validate_rejects_duplicate_worker_slugs_with_stage_slug_visible() -> None:
    profile = make_profile(
        stages=(
            ProfileStage(
                slug="stage1_foundation",
                node_name="stage1_foundation",
                next_stage_node="synthesis",
                prompt_file="stage1_foundation.md",
                workers=(
                    WorkerSpec(slug="duplicate", prompt_file="stage1/customer.md"),
                    WorkerSpec(slug="duplicate", prompt_file="stage1/regulatory.md"),
                ),
            ),
        )
    )

    with pytest.raises(ValueError, match="stage1_foundation"):
        profile.validate()


def test_existing_profiles_still_validate_unchanged() -> None:
    assert MARKET_ENTRY_PROFILE.validate() is MARKET_ENTRY_PROFILE
    assert PRICING_PROFILE.validate() is PRICING_PROFILE
    assert PROFITABILITY_PROFILE.validate() is PROFITABILITY_PROFILE

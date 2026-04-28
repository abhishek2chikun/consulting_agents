"""Pricing consulting profile."""

from __future__ import annotations

from app.agents._engine.profile import ConsultingProfile, ProfileStage

PRICING_PROFILE = ConsultingProfile(
    slug="pricing",
    display_name="Pricing",
    prompts_package="app.agents.pricing.prompts",
    framing_prompt="framing.md",
    stages=(
        ProfileStage(
            slug="stage1_value",
            node_name="stage1_value",
            next_stage_node="stage2_segments",
            prompt_file="stage1_value.md",
        ),
        ProfileStage(
            slug="stage2_segments",
            node_name="stage2_segments",
            next_stage_node="stage3_competitive",
            prompt_file="stage2_segments.md",
        ),
        ProfileStage(
            slug="stage3_competitive",
            node_name="stage3_competitive",
            next_stage_node="stage4_models",
            prompt_file="stage3_competitive.md",
        ),
        ProfileStage(
            slug="stage4_models",
            node_name="stage4_models",
            next_stage_node="stage5_rollout",
            prompt_file="stage4_models.md",
        ),
        ProfileStage(
            slug="stage5_rollout",
            node_name="stage5_rollout",
            next_stage_node="synthesis",
            prompt_file="stage5_rollout.md",
        ),
    ),
    reviewer_prompt_package="app.agents.pricing.prompts",
    reviewer_prompt="reviewer.md",
    reviewer_prompt_for_stage={
        "stage1_value": "reviewer_stage1_value.md",
        "stage2_segments": "reviewer_stage2_segments.md",
        "stage3_competitive": "reviewer_stage3_competitive.md",
        "stage4_models": "reviewer_stage4_models.md",
        "stage5_rollout": "reviewer_stage5_rollout.md",
    },
    synthesis_prompt="synthesis.md",
    audit_prompt="audit.md",
)

"""Profitability consulting profile (M9.2)."""

from __future__ import annotations

from app.agents._engine.profile import ConsultingProfile, ProfileStage

PROFITABILITY_PROFILE = ConsultingProfile(
    slug="profitability",
    display_name="Profitability",
    prompts_package="app.agents.profitability.prompts",
    framing_prompt="framing.md",
    stages=(
        ProfileStage(
            slug="stage1_revenue",
            node_name="stage1_revenue",
            next_stage_node="stage2_cost",
            prompt_file="stage1_revenue.md",
        ),
        ProfileStage(
            slug="stage2_cost",
            node_name="stage2_cost",
            next_stage_node="stage3_margin",
            prompt_file="stage2_cost.md",
        ),
        ProfileStage(
            slug="stage3_margin",
            node_name="stage3_margin",
            next_stage_node="stage4_competitor",
            prompt_file="stage3_margin.md",
        ),
        ProfileStage(
            slug="stage4_competitor",
            node_name="stage4_competitor",
            next_stage_node="stage5_levers",
            prompt_file="stage4_competitor.md",
        ),
        ProfileStage(
            slug="stage5_levers",
            node_name="stage5_levers",
            next_stage_node="synthesis",
            prompt_file="stage5_levers.md",
        ),
    ),
    reviewer_prompt_package="app.agents.profitability.prompts",
    reviewer_prompt="reviewer.md",
    reviewer_prompt_for_stage={
        "stage1_revenue": "reviewer_stage1_revenue.md",
        "stage2_cost": "reviewer_stage2_cost.md",
        "stage3_margin": "reviewer_stage3_margin.md",
        "stage4_competitor": "reviewer_stage4_competitor.md",
        "stage5_levers": "reviewer_stage5_levers.md",
    },
    synthesis_prompt="synthesis.md",
    audit_prompt="audit.md",
)

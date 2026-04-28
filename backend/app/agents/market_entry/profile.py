"""Market-entry consulting profile (M9.1)."""

from __future__ import annotations

from app.agents._engine.profile import ConsultingProfile, ProfileStage

MARKET_ENTRY_PROFILE = ConsultingProfile(
    slug="market_entry",
    display_name="Market Entry",
    prompts_package="app.agents.market_entry.prompts",
    framing_prompt="framing.md",
    stages=(
        ProfileStage(
            slug="stage1_foundation",
            node_name="stage1_foundation",
            next_stage_node="stage2_competitive",
            prompt_file="stage1_foundation.md",
        ),
        ProfileStage(
            slug="stage2_competitive",
            node_name="stage2_competitive",
            next_stage_node="stage3_risk",
            prompt_file="stage2_competitive.md",
        ),
        ProfileStage(
            slug="stage3_risk",
            node_name="stage3_risk",
            next_stage_node="stage4_demand",
            prompt_file="stage3_risk.md",
        ),
        ProfileStage(
            slug="stage4_demand",
            node_name="stage4_demand",
            next_stage_node="stage5_strategy",
            prompt_file="stage4_demand.md",
        ),
        ProfileStage(
            slug="stage5_strategy",
            node_name="stage5_strategy",
            next_stage_node="synthesis",
            prompt_file="stage5_strategy.md",
        ),
    ),
    reviewer_prompt_package="app.agents.market_entry.prompts",
    reviewer_prompt="reviewer.md",
    reviewer_prompt_for_stage={
        "stage1_foundation": "reviewer_stage1_foundation.md",
        "stage2_competitive": "reviewer_stage2_competitive.md",
        "stage3_risk": "reviewer_stage3_risk.md",
        "stage4_demand": "reviewer_stage4_demand.md",
        "stage5_strategy": "reviewer_stage5_strategy.md",
    },
    synthesis_prompt="synthesis.md",
    audit_prompt="audit.md",
)

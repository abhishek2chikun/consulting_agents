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
            next_stage_node="synthesis",
            prompt_file="stage3_risk.md",
        ),
    ),
    reviewer_prompt_package="app.agents.market_entry.prompts",
    reviewer_prompt="reviewer.md",
    synthesis_prompt="synthesis.md",
    audit_prompt="audit.md",
)

"""Market-entry consulting profile (M9.1)."""

from __future__ import annotations

from app.agents._engine.profile import ConsultingProfile, ProfileStage, WorkerSpec

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
            required_skills=("strategic-analysis", "market-sizing"),
            workers=(
                WorkerSpec(slug="market_sizing", prompt_file="stage1/market_sizing.md"),
                WorkerSpec(slug="customer", prompt_file="stage1/customer.md"),
                WorkerSpec(slug="regulatory", prompt_file="stage1/regulatory.md"),
            ),
        ),
        ProfileStage(
            slug="stage2_competitive",
            node_name="stage2_competitive",
            next_stage_node="stage3_risk",
            prompt_file="stage2_competitive.md",
            required_skills=("strategic-analysis", "competitive-intelligence"),
            workers=(
                WorkerSpec(slug="competitor", prompt_file="stage2/competitor.md"),
                WorkerSpec(slug="channel", prompt_file="stage2/channel.md"),
                WorkerSpec(slug="pricing", prompt_file="stage2/pricing.md"),
            ),
            max_retries=5,
        ),
        ProfileStage(
            slug="stage3_risk",
            node_name="stage3_risk",
            next_stage_node="stage4_demand",
            prompt_file="stage3_risk.md",
            required_skills=("due-diligence", "evidence-discipline"),
            workers=(
                WorkerSpec(slug="risk", prompt_file="stage3/risk.md"),
                WorkerSpec(slug="regulatory_risk", prompt_file="stage3_risk/regulatory_risk.md"),
                WorkerSpec(slug="operational_risk", prompt_file="stage3_risk/operational_risk.md"),
            ),
        ),
        ProfileStage(
            slug="stage4_demand",
            node_name="stage4_demand",
            next_stage_node="stage5_strategy",
            prompt_file="stage4_demand.md",
            required_skills=("market-sizing", "evidence-discipline"),
            workers=(
                WorkerSpec(slug="demand_drivers", prompt_file="stage4_demand/demand_drivers.md"),
                WorkerSpec(
                    slug="willingness_to_pay",
                    prompt_file="stage4_demand/willingness_to_pay.md",
                ),
                WorkerSpec(
                    slug="segment_priority",
                    prompt_file="stage4_demand/segment_priority.md",
                ),
            ),
        ),
        ProfileStage(
            slug="stage5_strategy",
            node_name="stage5_strategy",
            next_stage_node="synthesis",
            prompt_file="stage5_strategy.md",
            required_skills=("strategic-analysis", "implementation-planning"),
            workers=(
                WorkerSpec(slug="go_to_market", prompt_file="stage5_strategy/go_to_market.md"),
                WorkerSpec(slug="partnerships", prompt_file="stage5_strategy/partnerships.md"),
                WorkerSpec(slug="milestones", prompt_file="stage5_strategy/milestones.md"),
            ),
        ),
    ),
    reviewer_prompt_package="app.agents.market_entry.prompts",
    reviewer_prompt="reviewer.md",
    framing_skills=("strategic-analysis",),
    synthesis_skills=("client-deliverables", "writing-style"),
    audit_skills=("due-diligence", "evidence-discipline"),
    reviewer_skills_per_stage={
        "stage1_foundation": ("strategic-analysis", "market-sizing"),
        "stage2_competitive": ("strategic-analysis", "competitive-intelligence"),
        "stage3_risk": ("due-diligence", "evidence-discipline"),
        "stage4_demand": ("market-sizing", "evidence-discipline"),
        "stage5_strategy": ("strategic-analysis", "implementation-planning"),
    },
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

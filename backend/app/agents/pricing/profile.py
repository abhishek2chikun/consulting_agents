"""Pricing consulting profile."""

from __future__ import annotations

from app.agents._engine.profile import ConsultingProfile, ProfileStage, WorkerSpec

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
            required_skills=("strategic-analysis", "evidence-discipline"),
            workers=(
                WorkerSpec(slug="value_drivers", prompt_file="stage1_value/value_drivers.md"),
                WorkerSpec(
                    slug="value_quantification",
                    prompt_file="stage1_value/value_quantification.md",
                ),
                WorkerSpec(
                    slug="customer_perception",
                    prompt_file="stage1_value/customer_perception.md",
                ),
            ),
        ),
        ProfileStage(
            slug="stage2_segments",
            node_name="stage2_segments",
            next_stage_node="stage3_competitive",
            prompt_file="stage2_segments.md",
            required_skills=("strategic-analysis", "market-sizing"),
            workers=(
                WorkerSpec(slug="segmentation", prompt_file="stage2_segments/segmentation.md"),
                WorkerSpec(
                    slug="willingness_to_pay",
                    prompt_file="stage2_segments/willingness_to_pay.md",
                ),
                WorkerSpec(
                    slug="segment_priority",
                    prompt_file="stage2_segments/segment_priority.md",
                ),
            ),
            max_retries=5,
        ),
        ProfileStage(
            slug="stage3_competitive",
            node_name="stage3_competitive",
            next_stage_node="stage4_models",
            prompt_file="stage3_competitive.md",
            required_skills=("competitive-intelligence", "engagement-pricing"),
            workers=(
                WorkerSpec(
                    slug="competitor_pricing",
                    prompt_file="stage3_competitive/competitor_pricing.md",
                ),
                WorkerSpec(slug="positioning", prompt_file="stage3_competitive/positioning.md"),
                WorkerSpec(
                    slug="share_dynamics",
                    prompt_file="stage3_competitive/share_dynamics.md",
                ),
            ),
        ),
        ProfileStage(
            slug="stage4_models",
            node_name="stage4_models",
            next_stage_node="stage5_rollout",
            prompt_file="stage4_models.md",
            required_skills=("engagement-pricing", "financial-modeling"),
            workers=(
                WorkerSpec(slug="pricing_models", prompt_file="stage4_models/pricing_models.md"),
                WorkerSpec(
                    slug="financial_impact",
                    prompt_file="stage4_models/financial_impact.md",
                ),
                WorkerSpec(slug="packaging", prompt_file="stage4_models/packaging.md"),
            ),
        ),
        ProfileStage(
            slug="stage5_rollout",
            node_name="stage5_rollout",
            next_stage_node="synthesis",
            prompt_file="stage5_rollout.md",
            required_skills=("implementation-planning", "change-management"),
            workers=(
                WorkerSpec(slug="rollout_plan", prompt_file="stage5_rollout/rollout_plan.md"),
                WorkerSpec(
                    slug="change_management",
                    prompt_file="stage5_rollout/change_management.md",
                ),
                WorkerSpec(slug="monitoring", prompt_file="stage5_rollout/monitoring.md"),
            ),
        ),
    ),
    reviewer_prompt_package="app.agents.pricing.prompts",
    reviewer_prompt="reviewer.md",
    framing_skills=("strategic-analysis",),
    synthesis_skills=("client-deliverables", "writing-style"),
    audit_skills=("due-diligence", "evidence-discipline"),
    reviewer_skills_per_stage={
        "stage1_value": ("strategic-analysis", "evidence-discipline"),
        "stage2_segments": ("strategic-analysis", "market-sizing"),
        "stage3_competitive": ("competitive-intelligence", "engagement-pricing"),
        "stage4_models": ("engagement-pricing", "financial-modeling"),
        "stage5_rollout": ("implementation-planning", "change-management"),
    },
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

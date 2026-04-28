"""Profitability consulting profile (M9.2)."""

from __future__ import annotations

from app.agents._engine.profile import ConsultingProfile, ProfileStage, WorkerSpec

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
            required_skills=("financial-modeling", "market-sizing"),
            workers=(
                WorkerSpec(
                    slug="revenue_decomposition",
                    prompt_file="stage1_revenue/revenue_decomposition.md",
                ),
                WorkerSpec(slug="growth_drivers", prompt_file="stage1_revenue/growth_drivers.md"),
                WorkerSpec(
                    slug="customer_segments",
                    prompt_file="stage1_revenue/customer_segments.md",
                ),
            ),
        ),
        ProfileStage(
            slug="stage2_cost",
            node_name="stage2_cost",
            next_stage_node="stage3_margin",
            prompt_file="stage2_cost.md",
            required_skills=("financial-modeling", "process-excellence"),
            workers=(
                WorkerSpec(slug="cost_structure", prompt_file="stage2_cost/cost_structure.md"),
                WorkerSpec(
                    slug="fixed_vs_variable",
                    prompt_file="stage2_cost/fixed_vs_variable.md",
                ),
                WorkerSpec(slug="cost_drivers", prompt_file="stage2_cost/cost_drivers.md"),
            ),
            max_retries=5,
        ),
        ProfileStage(
            slug="stage3_margin",
            node_name="stage3_margin",
            next_stage_node="stage4_competitor",
            prompt_file="stage3_margin.md",
            required_skills=("financial-modeling", "unit-economics"),
            workers=(
                WorkerSpec(slug="margin_walk", prompt_file="stage3_margin/margin_walk.md"),
                WorkerSpec(
                    slug="unit_economics",
                    prompt_file="stage3_margin/unit_economics.md",
                ),
                WorkerSpec(slug="benchmarks", prompt_file="stage3_margin/benchmarks.md"),
            ),
        ),
        ProfileStage(
            slug="stage4_competitor",
            node_name="stage4_competitor",
            next_stage_node="stage5_levers",
            prompt_file="stage4_competitor.md",
            required_skills=("competitive-intelligence", "evidence-discipline"),
            workers=(
                WorkerSpec(
                    slug="peer_benchmarks",
                    prompt_file="stage4_competitor/peer_benchmarks.md",
                ),
                WorkerSpec(
                    slug="structural_advantages",
                    prompt_file="stage4_competitor/structural_advantages.md",
                ),
                WorkerSpec(slug="gap_analysis", prompt_file="stage4_competitor/gap_analysis.md"),
            ),
        ),
        ProfileStage(
            slug="stage5_levers",
            node_name="stage5_levers",
            next_stage_node="synthesis",
            prompt_file="stage5_levers.md",
            required_skills=("strategic-analysis", "implementation-planning"),
            workers=(
                WorkerSpec(
                    slug="lever_inventory",
                    prompt_file="stage5_levers/lever_inventory.md",
                ),
                WorkerSpec(slug="prioritization", prompt_file="stage5_levers/prioritization.md"),
                WorkerSpec(slug="roadmap", prompt_file="stage5_levers/roadmap.md"),
            ),
        ),
    ),
    reviewer_prompt_package="app.agents.profitability.prompts",
    reviewer_prompt="reviewer.md",
    framing_skills=("strategic-analysis",),
    synthesis_skills=("client-deliverables", "writing-style"),
    audit_skills=("due-diligence", "evidence-discipline"),
    reviewer_skills_per_stage={
        "stage1_revenue": ("financial-modeling", "market-sizing"),
        "stage2_cost": ("financial-modeling", "process-excellence"),
        "stage3_margin": ("financial-modeling", "unit-economics"),
        "stage4_competitor": ("competitive-intelligence", "evidence-discipline"),
        "stage5_levers": ("strategic-analysis", "implementation-planning"),
    },
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

"""V1.6 smoke test for the pricing profile."""

from __future__ import annotations

import pytest

from app.agents._engine.registry import get_profile
from app.workers import run_worker
from app.workers.run_worker import continue_after_framing, start_framing
from tests.integration.v16_smoke_helpers import (
    ProfileSmokeSpec,
    RecordingTool,
    ScriptedResearchModel,
    agent_id_from_messages,
    artifact_content,
    build_final_report,
    build_models,
    cleanup_run,
    create_run,
    run_summary,
    system_prompt_text,
)


@pytest.mark.asyncio
async def test_pricing_v16_profile_runs_with_workers_and_stage_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = ProfileSmokeSpec(
        task_type="pricing",
        goal="Design an enterprise SaaS pricing strategy",
        answer_key="pricing_scope",
        answer_value="Enterprise SaaS",
        framing_response={
            "brief": {
                "objective": "Validate pricing strategy",
                "target_market": "Enterprise SaaS",
                "constraints": [],
                "questionnaire_answers": {},
            },
            "questionnaire": {
                "items": [
                    {
                        "id": "pricing_scope",
                        "label": "Which product or segment should we price?",
                        "type": "text",
                        "required": True,
                    }
                ]
            },
        },
        stage_slugs=(
            "stage1_value",
            "stage2_segments",
            "stage3_competitive",
            "stage4_models",
            "stage5_rollout",
        ),
        workers_by_stage={
            "stage1_value": ("value_drivers", "value_quantification", "customer_perception"),
            "stage2_segments": ("segmentation", "willingness_to_pay", "segment_priority"),
            "stage3_competitive": ("competitor_pricing", "positioning", "share_dynamics"),
            "stage4_models": ("pricing_models", "financial_impact", "packaging"),
            "stage5_rollout": ("rollout_plan", "change_management", "monitoring"),
        },
        stage_required_skill_titles={
            "stage1_value": ("Strategic Analysis", "Evidence Discipline"),
            "stage2_segments": ("Strategic Analysis", "Market Sizing"),
            "stage3_competitive": ("Competitive Intelligence", "Engagement Pricing"),
            "stage4_models": ("Engagement Pricing", "Financial Modeling"),
            "stage5_rollout": ("Implementation Planning", "Change Management"),
        },
        reviewer_skill_titles={
            "stage1_value": ("Strategic Analysis", "Evidence Discipline"),
            "stage2_segments": ("Strategic Analysis", "Market Sizing"),
            "stage3_competitive": ("Competitive Intelligence", "Engagement Pricing"),
            "stage4_models": ("Engagement Pricing", "Financial Modeling"),
            "stage5_rollout": ("Implementation Planning", "Change Management"),
        },
        framing_skill_titles=("Strategic Analysis",),
        synthesis_skill_titles=("Client Deliverables", "Writing Style"),
        audit_skill_titles=("Due Diligence", "Evidence Discipline"),
        tool_agents=(
            "stage1_value.value_drivers",
            "stage2_segments.segmentation",
            "stage3_competitive.competitor_pricing",
        ),
        final_report_heading="Pricing Final Report",
    )
    models = build_models(spec)
    tools = [RecordingTool("web_search"), RecordingTool("rag_search")]
    monkeypatch.setattr(
        run_worker,
        "build_tools_factory",
        lambda *_args, **_kwargs: lambda: tools,
        raising=False,
    )

    def factory(role: str) -> object:
        return models[role]

    profile = get_profile(spec.task_type)
    assert profile is not None
    run_id = await create_run(task_type=spec.task_type, goal=spec.goal)
    try:
        await start_framing(run_id, profile=profile, model_factory=factory)
        await continue_after_framing(
            run_id,
            answers={spec.answer_key: spec.answer_value},
            profile=profile,
            model_factory=factory,
        )

        artifact_paths, gates, events = await run_summary(run_id)
        assert "final_report.md" in artifact_paths
        report_content = await artifact_content(run_id, "final_report.md")
        assert report_content.startswith(build_final_report(spec).rstrip())
        assert "## Sources" in report_content
        assert len(gates) == 5
        assert {gate.stage for gate in gates} == set(spec.stage_slugs)
        assert all(gate.verdict == "advance" for gate in gates)

        rich_stages = 0
        for stage_slug in spec.stage_slugs:
            stage_paths = [path for path in artifact_paths if path.startswith(f"{stage_slug}/")]
            if len(stage_paths) >= 4:
                rich_stages += 1
            for worker_slug in spec.workers_by_stage[stage_slug]:
                assert any(path.startswith(f"{stage_slug}/{worker_slug}/") for path in stage_paths)
        assert rich_stages >= 3

        framing_prompt = system_prompt_text(models["framing"], structured=True)
        assert "Applicable Consulting Skills" in framing_prompt
        for skill_title in spec.framing_skill_titles:
            assert skill_title in framing_prompt
        research_model = models["research"]
        assert isinstance(research_model, ScriptedResearchModel)
        prompts = {
            agent_id_from_messages(messages): str(messages[0].content)
            for _, messages in research_model.structured_calls
        }
        for stage_slug, skill_titles in spec.stage_required_skill_titles.items():
            prompt = prompts[f"{stage_slug}.{spec.workers_by_stage[stage_slug][0]}"]
            for skill_title in skill_titles:
                assert skill_title in prompt

        reviewer_prompts = [
            str(messages[0].content) for _, messages in models["reviewer"].structured_calls
        ]
        for prompt, stage_slug in zip(reviewer_prompts, spec.stage_slugs, strict=False):
            for skill_title in spec.reviewer_skill_titles[stage_slug]:
                assert skill_title in prompt

        for skill_title in spec.synthesis_skill_titles:
            assert skill_title in system_prompt_text(models["synthesis"], structured=False)
        for skill_title in spec.audit_skill_titles:
            assert skill_title in system_prompt_text(models["audit"], structured=False)

        assert {call["agent_id"] for call in tools[0].calls} == set(spec.tool_agents)
        assert tools[1].calls == []
        warning_agents = {
            event.agent
            for event in events
            if event.type == "agent_message"
            and "without tool use" in str((event.payload or {}).get("text", ""))
        }
        for agent_id in spec.tool_agents:
            assert agent_id not in warning_agents
    finally:
        await cleanup_run(run_id)

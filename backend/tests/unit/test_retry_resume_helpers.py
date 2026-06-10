"""Unit tests for run retry resume helpers."""

from __future__ import annotations

from app.agents._engine.profile import ConsultingProfile, ProfileStage, WorkerSpec
from app.agents._engine.state import GateVerdict
from app.workers.run_worker import _resume_target_agents


def _profile() -> ConsultingProfile:
    return ConsultingProfile(
        slug="test",
        display_name="Test",
        prompts_package="app.agents.market_entry.prompts",
        framing_prompt="framing.md",
        stages=(
            ProfileStage(
                slug="stage1",
                node_name="stage1_node",
                next_stage_node="stage2_node",
                prompt_file="stage1.md",
                workers=(WorkerSpec(slug="worker_a", prompt_file="a.md"),),
            ),
            ProfileStage(
                slug="stage2",
                node_name="stage2_node",
                next_stage_node="synthesis",
                prompt_file="stage2.md",
                workers=(
                    WorkerSpec(slug="pricing", prompt_file="pricing.md"),
                    WorkerSpec(slug="channel", prompt_file="channel.md"),
                ),
            ),
        ),
        reviewer_prompt_package="app.agents.market_entry.prompts",
        reviewer_prompt="reviewer.md",
        synthesis_prompt="synthesis.md",
        audit_prompt="audit.md",
    )


def test_resume_target_agents_restores_reiterate_scope() -> None:
    gate_verdicts: dict[str, GateVerdict] = {
        "stage2": {
            "verdict": "reiterate",
            "stage": "stage2",
            "attempt": 1,
            "gaps": ["pricing gap"],
            "target_agents": ["pricing"],
            "rationale": "fix pricing",
        }
    }

    assert (
        _resume_target_agents(
            _profile(),
            entry_node="stage2_node",
            gate_verdicts=gate_verdicts,
        )
        == ["pricing"]
    )


def test_resume_target_agents_none_for_advance_or_non_stage_entry() -> None:
    gate_verdicts: dict[str, GateVerdict] = {
        "stage2": {
            "verdict": "advance",
            "stage": "stage2",
            "attempt": 1,
            "gaps": [],
            "target_agents": [],
            "rationale": "ok",
        }
    }

    assert (
        _resume_target_agents(
            _profile(),
            entry_node="stage2_node",
            gate_verdicts=gate_verdicts,
        )
        is None
    )
    assert (
        _resume_target_agents(
            _profile(),
            entry_node="synthesis",
            gate_verdicts=gate_verdicts,
        )
        is None
    )

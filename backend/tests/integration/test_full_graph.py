"""End-to-end smoke test for the M6.10 full graph pipeline."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.agents.market_entry.graph import build_full_graph
from app.core.db import AsyncSessionLocal
from app.models import (
    SINGLETON_USER_ID,
    Artifact,
    Evidence,
    EvidenceKind,
    Gate,
    Run,
    RunStatus,
)
from app.testing.fake_chat_model import FakeChatModel


@pytest_asyncio.fixture
async def fresh_run() -> AsyncIterator[uuid.UUID]:
    async with AsyncSessionLocal() as session:
        run = Run(
            user_id=SINGLETON_USER_ID,
            task_id="market_entry",
            goal="Enter EU EV-charging market",
            status=RunStatus.questioning,
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        yield run.id


def _stage_payload(stage_slug: str, src_id: str) -> dict:
    return {
        "artifacts": [
            {
                "path": f"{stage_slug}/findings.md",
                "content": f"{stage_slug} finding [^{src_id}].",
                "kind": "markdown",
            }
        ],
        "evidence": [
            {
                "src_id": src_id,
                "title": f"{stage_slug} source",
                "url": f"https://example.com/{src_id}",
                "snippet": "snippet",
                "kind": "web",
                "provider": "tavily",
            }
        ],
        "summary": f"{stage_slug} done",
    }


def _gate_payload(stage: str, verdict: str, target_agents: list[str] | None = None) -> dict:
    return {
        "verdict": verdict,
        "stage": stage,
        "attempt": 1,
        "gaps": [] if verdict == "advance" else ["something"],
        "target_agents": target_agents or [],
        "rationale": "ok" if verdict == "advance" else "needs work",
    }


@pytest.mark.asyncio
async def test_full_graph_runs_end_to_end_with_one_stage2_reiterate(
    fresh_run: uuid.UUID,
) -> None:
    # Pre-stage a doc-evidence row so synthesis can also cite [^doc1] if it
    # chooses; not required, just exercises the lookup path.

    framing_response = {
        "brief": {
            "objective": "Assess EU EV-charging entry",
            "target_market": "EU",
            "constraints": [],
            "questionnaire_answers": {},
        },
        "questionnaire": {"items": []},
    }

    # Per-role scripted models. We need to pre-script every call the
    # graph will make:
    #   framing  : 1 structured call
    #   research : stage1, stage2 (1st), stage2 (reiterate), stage3, stage4, stage5 -> 6 calls
    #   reviewer : stage1, stage2 (reiterate), stage2 (advance), stage3,
    #              stage4, stage5 -> 6 calls
    #   synthesis: 1 plain text call
    #   audit    : 1 plain text call
    framing_model = FakeChatModel(structured_responses=[framing_response])
    research_model = FakeChatModel(
        structured_responses=[
            _stage_payload("stage1_foundation", "s1"),
            _stage_payload("stage2_competitive", "s2"),
            _stage_payload("stage2_competitive", "s2b"),
            _stage_payload("stage3_risk", "s3"),
            _stage_payload("stage4_demand", "s4"),
            _stage_payload("stage5_strategy", "s5"),
        ]
    )
    reviewer_model = FakeChatModel(
        structured_responses=[
            _gate_payload("stage1_foundation", "advance"),
            _gate_payload("stage2_competitive", "reiterate", ["pricing"]),
            _gate_payload("stage2_competitive", "advance"),
            _gate_payload("stage3_risk", "advance"),
            _gate_payload("stage4_demand", "advance"),
            _gate_payload("stage5_strategy", "advance"),
        ]
    )
    report_body = (
        "# Final Report\n\n"
        "## Executive Summary\n"
        "- Foundation finding [^s1].\n"
        "- Competitive finding [^s2b].\n"
        "- Risk finding [^s3].\n"
        "- Demand finding [^s4].\n"
        "- Strategy finding [^s5].\n"
    )
    synthesis_model = FakeChatModel(responses=[report_body])
    audit_model = FakeChatModel(
        responses=["## Weak Claims\n- none\n## Contradictions\n- none\n## Residual Gaps\n- none\n"]
    )

    models_by_role: dict[str, FakeChatModel] = {
        "framing": framing_model,
        "research": research_model,
        "reviewer": reviewer_model,
        "synthesis": synthesis_model,
        "audit": audit_model,
    }

    def model_factory(role: str) -> object:
        return models_by_role[role]

    graph = build_full_graph(
        model_factory=model_factory,
        checkpointer=None,
        max_stage_retries=2,
    )

    final_state = await graph.ainvoke(
        {
            "run_id": str(fresh_run),
            "goal": "Enter EU EV-charging market",
        }
    )

    # Stage2 ran twice (initial + reiterate)
    assert (final_state.get("stage_attempts") or {}).get("stage2_competitive") in (
        2,
        # When reviewer_stage2 advances on the 2nd attempt, attempts is not
        # bumped further. So we expect == 2.
    )

    # All artifact files persisted
    async with AsyncSessionLocal() as session:
        artifact_paths = sorted(
            r.path
            for r in (await session.execute(select(Artifact).where(Artifact.run_id == fresh_run)))
            .scalars()
            .all()
        )
        gate_count = len(
            (await session.execute(select(Gate).where(Gate.run_id == fresh_run))).scalars().all()
        )
        evidence_count = len(
            (await session.execute(select(Evidence).where(Evidence.run_id == fresh_run)))
            .scalars()
            .all()
        )
        run = await session.get(Run, fresh_run)

    assert "framing/questionnaire.json" in artifact_paths
    assert "stage1_foundation/findings.md" in artifact_paths
    assert "stage2_competitive/findings.md" in artifact_paths
    assert "stage3_risk/findings.md" in artifact_paths
    assert "stage4_demand/findings.md" in artifact_paths
    assert "stage5_strategy/findings.md" in artifact_paths
    assert "final_report.md" in artifact_paths
    assert "audit.md" in artifact_paths
    # 6 gate decisions written
    assert gate_count == 6
    # 6 distinct src_ids cited
    assert evidence_count == 6
    assert run is not None
    assert run.status == RunStatus.completed

    # Sanity: every scripted call was consumed.
    for role, m in models_by_role.items():
        assert not m.structured_responses, f"{role} structured queue not drained"
        assert not m.responses, f"{role} text queue not drained"

    # Verify EvidenceKind enum coercion succeeded for at least one row
    async with AsyncSessionLocal() as session:
        rows = (
            (await session.execute(select(Evidence).where(Evidence.run_id == fresh_run)))
            .scalars()
            .all()
        )
    assert all(r.kind == EvidenceKind.web for r in rows)

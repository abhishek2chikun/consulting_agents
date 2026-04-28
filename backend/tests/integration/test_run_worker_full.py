"""M6.11 — run_worker drives the full graph end-to-end.

The worker is responsible for:

  * `start_framing(run_id, *, model_factory)` — runs only the framing node,
    persists the questionnaire artifact, leaves the run in `questioning`
    (waiting for the human to submit answers).
  * `continue_after_framing(run_id, answers, *, model_factory)` — drives
    the full pipeline (stages → reviewers → synthesis → audit). It steps
    via `astream()` and polls `Run.status == cancelling` between nodes
    so a `POST /runs/{id}/cancel` can take effect cooperatively.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.agents.market_entry.profile import MARKET_ENTRY_PROFILE
from app.core.db import AsyncSessionLocal
from app.models import (
    SINGLETON_USER_ID,
    Artifact,
    Event,
    Gate,
    Message,
    MessageRole,
    Run,
    RunStatus,
)
from app.testing.fake_chat_model import FakeChatModel
from app.workers.run_worker import continue_after_framing, start_framing
from tests.integration.v16_smoke_helpers import ScriptedResearchModel


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


def _stage_payload(agent_id: str, src_id: str) -> dict:
    _stage_slug, worker_slug = agent_id.split(".", 1)
    return {
        "artifacts": [
            {
                "path": "findings.md",
                "content": f"{agent_id} finding [^{src_id}].",
                "kind": "markdown",
            }
        ],
        "evidence": [
            {
                "src_id": src_id,
                "title": f"{worker_slug} source",
                "url": f"https://example.com/{src_id}",
                "snippet": "snippet",
                "kind": "web",
                "provider": "tavily",
            }
        ],
        "summary": f"{agent_id} summary",
    }


def _gate(stage: str, verdict: str) -> dict:
    return {
        "verdict": verdict,
        "stage": stage,
        "attempt": 1,
        "gaps": [] if verdict == "advance" else ["gap"],
        "target_agents": [],
        "rationale": "ok",
    }


def _build_factories(
    *,
    framing_questionnaire: dict | None = None,
    stage_payloads: dict[str, list[dict]] | None = None,
    gate_verdicts: dict[str, list[dict]] | None = None,
    synthesis_text: str | None = None,
    audit_text: str | None = None,
) -> tuple[dict[str, FakeChatModel], object]:
    """Build a per-role registry of `FakeChatModel`s + a `model_factory`."""

    framing_response = {
        "brief": {
            "objective": "Assess EU EV-charging entry",
            "target_market": "EU",
            "constraints": [],
            "questionnaire_answers": {},
        },
        "questionnaire": framing_questionnaire
        or {
            "items": [
                {
                    "id": "time_horizon",
                    "label": "Time horizon",
                    "type": "text",
                    "required": True,
                }
            ]
        },
    }

    stages = stage_payloads or {
        "stage1_foundation.market_sizing": [
            _stage_payload("stage1_foundation.market_sizing", "s1")
        ],
        "stage1_foundation.customer": [_stage_payload("stage1_foundation.customer", "s2")],
        "stage1_foundation.regulatory": [_stage_payload("stage1_foundation.regulatory", "s3")],
        "stage2_competitive.competitor": [_stage_payload("stage2_competitive.competitor", "s4")],
        "stage2_competitive.channel": [_stage_payload("stage2_competitive.channel", "s5")],
        "stage2_competitive.pricing": [_stage_payload("stage2_competitive.pricing", "s6")],
        "stage3_risk.risk": [_stage_payload("stage3_risk.risk", "s7")],
        "stage3_risk.regulatory_risk": [_stage_payload("stage3_risk.regulatory_risk", "s8")],
        "stage3_risk.operational_risk": [_stage_payload("stage3_risk.operational_risk", "s9")],
        "stage4_demand.demand_drivers": [_stage_payload("stage4_demand.demand_drivers", "s10")],
        "stage4_demand.willingness_to_pay": [
            _stage_payload("stage4_demand.willingness_to_pay", "s11")
        ],
        "stage4_demand.segment_priority": [_stage_payload("stage4_demand.segment_priority", "s12")],
        "stage5_strategy.go_to_market": [_stage_payload("stage5_strategy.go_to_market", "s13")],
        "stage5_strategy.partnerships": [_stage_payload("stage5_strategy.partnerships", "s14")],
        "stage5_strategy.milestones": [_stage_payload("stage5_strategy.milestones", "s15")],
    }
    structured_by_agent = {agent_id: payloads[0] for agent_id, payloads in stages.items()}

    gates = gate_verdicts or {
        "stage1_foundation": [_gate("stage1_foundation", "advance")],
        "stage2_competitive": [_gate("stage2_competitive", "advance")],
        "stage3_risk": [_gate("stage3_risk", "advance")],
        "stage4_demand": [_gate("stage4_demand", "advance")],
        "stage5_strategy": [_gate("stage5_strategy", "advance")],
    }
    reviewer_queue = (
        gates["stage1_foundation"]
        + gates["stage2_competitive"]
        + gates["stage3_risk"]
        + gates["stage4_demand"]
        + gates["stage5_strategy"]
    )

    framing_model = FakeChatModel(structured_responses=[framing_response])
    research_model = ScriptedResearchModel(
        tool_calls_by_agent={},
        structured_responses_by_agent=structured_by_agent,
    )
    reviewer_model = FakeChatModel(structured_responses=reviewer_queue)
    synthesis_model = FakeChatModel(
        responses=[
            synthesis_text
            or (
                "# Final Report\n\n## Executive Summary\n"
                "- s1 [^s1] s2 [^s4] s3 [^s7] s4 [^s10] s5 [^s13].\n"
            )
        ]
    )
    audit_model = FakeChatModel(
        responses=[
            audit_text
            or "## Weak Claims\n- none\n## Contradictions\n- none\n## Residual Gaps\n- none\n"
        ]
    )

    models = {
        "framing": framing_model,
        "research": research_model,
        "reviewer": reviewer_model,
        "synthesis": synthesis_model,
        "audit": audit_model,
    }

    def factory(role: str) -> object:
        return models[role]

    return models, factory


# ---------------------------------------------------------------------------
# start_framing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_framing_runs_node_and_persists_questionnaire(
    fresh_run: uuid.UUID,
) -> None:
    models, factory = _build_factories(
        framing_questionnaire={
            "items": [
                {
                    "id": "geography",
                    "label": "Which geography?",
                    "type": "text",
                    "required": True,
                }
            ]
        }
    )

    await start_framing(fresh_run, profile=MARKET_ENTRY_PROFILE, model_factory=factory)

    async with AsyncSessionLocal() as session:
        artifact = (
            await session.execute(
                select(Artifact).where(
                    Artifact.run_id == fresh_run,
                    Artifact.path == "framing/questionnaire.json",
                )
            )
        ).scalar_one()
        run = await session.get(Run, fresh_run)

    assert "Which geography?" in artifact.content
    # Run stays in `questioning` until the human submits answers
    assert run is not None
    assert run.status == RunStatus.questioning
    # The framing model was actually called
    assert not models["framing"].structured_responses


# ---------------------------------------------------------------------------
# continue_after_framing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_continue_after_framing_drives_full_pipeline_to_completed(
    fresh_run: uuid.UUID,
) -> None:
    # Pre-stage: caller has already invoked start_framing and persisted the
    # questionnaire artifact. We seed it directly to keep the test focused.
    async with AsyncSessionLocal() as session:
        session.add(
            Artifact(
                run_id=fresh_run,
                path="framing/questionnaire.json",
                kind="json",
                content='{"items": []}',
            )
        )
        await session.commit()

    # Continuation skips framing, so its scripted response queue is empty.
    models, factory = _build_factories()
    models["framing"].structured_responses.clear()

    await continue_after_framing(
        fresh_run,
        answers={"time_horizon": "12 months"},
        profile=MARKET_ENTRY_PROFILE,
        model_factory=factory,
    )

    async with AsyncSessionLocal() as session:
        run = await session.get(Run, fresh_run)
        artifact_paths = sorted(
            r.path
            for r in (await session.execute(select(Artifact).where(Artifact.run_id == fresh_run)))
            .scalars()
            .all()
        )
        gate_count = len(
            (await session.execute(select(Gate).where(Gate.run_id == fresh_run))).scalars().all()
        )
        message_count = len(
            (
                await session.execute(
                    select(Message).where(
                        Message.run_id == fresh_run,
                        Message.role == MessageRole.user,
                    )
                )
            )
            .scalars()
            .all()
        )

    assert run is not None
    assert run.status == RunStatus.completed
    assert any(path.startswith("stage1_foundation/") for path in artifact_paths)
    assert any(path.startswith("stage2_competitive/") for path in artifact_paths)
    assert any(path.startswith("stage3_risk/") for path in artifact_paths)
    assert any(path.startswith("stage4_demand/") for path in artifact_paths)
    assert any(path.startswith("stage5_strategy/") for path in artifact_paths)
    assert "final_report.md" in artifact_paths
    assert "audit.md" in artifact_paths
    assert gate_count == 5
    # Answers persisted as a single user message
    assert message_count == 1


# ---------------------------------------------------------------------------
# cancel
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_continue_after_framing_honors_cooperative_cancel(
    fresh_run: uuid.UUID,
) -> None:
    """Flipping `Run.status -> cancelling` mid-run aborts before the next node."""

    async with AsyncSessionLocal() as session:
        session.add(
            Artifact(
                run_id=fresh_run,
                path="framing/questionnaire.json",
                kind="json",
                content='{"items": []}',
            )
        )
        await session.commit()

    models, factory = _build_factories()
    models["framing"].structured_responses.clear()

    # We schedule a cancellation flip to fire as soon as the worker starts.
    async def _flip_to_cancelling() -> None:
        # Yield once so the worker has a chance to begin running.
        await asyncio.sleep(0.05)
        async with AsyncSessionLocal() as session:
            run = await session.get(Run, fresh_run)
            assert run is not None
            run.status = RunStatus.cancelling
            await session.commit()

    flipper = asyncio.create_task(_flip_to_cancelling())
    try:
        await continue_after_framing(
            fresh_run,
            answers={"time_horizon": "12 months"},
            profile=MARKET_ENTRY_PROFILE,
            model_factory=factory,
        )
    finally:
        await flipper

    async with AsyncSessionLocal() as session:
        run = await session.get(Run, fresh_run)
        run_cancelled_events = (
            (
                await session.execute(
                    select(Event).where(
                        Event.run_id == fresh_run,
                        Event.type == "run_cancelled",
                    )
                )
            )
            .scalars()
            .all()
        )

    assert run is not None
    assert run.status == RunStatus.cancelled
    assert len(run_cancelled_events) == 1


@pytest.mark.asyncio
async def test_continue_after_framing_marks_cancelled_when_task_is_cancelled(
    fresh_run: uuid.UUID,
) -> None:
    """Direct Task.cancel() from the API registry must not leave status stuck."""

    async with AsyncSessionLocal() as session:
        session.add(
            Artifact(
                run_id=fresh_run,
                path="framing/questionnaire.json",
                kind="json",
                content='{"items": []}',
            )
        )
        await session.commit()

    class BlockingStructuredModel:
        def with_structured_output(self, _schema: object) -> BlockingStructuredModel:
            return self

        async def ainvoke(self, _messages: object) -> object:
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

    def factory(_role: str) -> object:
        return BlockingStructuredModel()

    task = asyncio.create_task(
        continue_after_framing(
            fresh_run,
            answers={"time_horizon": "12 months"},
            profile=MARKET_ENTRY_PROFILE,
            model_factory=factory,
        )
    )
    await asyncio.sleep(0.05)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task

    async with AsyncSessionLocal() as session:
        run = await session.get(Run, fresh_run)
        run_cancelled_events = (
            (
                await session.execute(
                    select(Event).where(
                        Event.run_id == fresh_run,
                        Event.type == "run_cancelled",
                    )
                )
            )
            .scalars()
            .all()
        )

    assert run is not None
    assert run.status == RunStatus.cancelled
    assert len(run_cancelled_events) == 1

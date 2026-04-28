"""Integration tests for M6.5–M6.7 stage research nodes."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.agents._engine.profile import ConsultingProfile, ProfileStage
from app.agents.market_entry.nodes.stage import make_stage_node
from app.agents.market_entry.state import RunState
from app.core.db import AsyncSessionLocal
from app.models import SINGLETON_USER_ID, Artifact, Evidence, Run, RunStatus
from app.testing.fake_chat_model import FakeChatModel


def _profile_without_workers(stage_slug: str) -> ConsultingProfile:
    return ConsultingProfile(
        slug="test_stage_profile",
        display_name="Test Stage Profile",
        prompts_package="app.agents.market_entry.prompts",
        framing_prompt="framing.md",
        stages=(
            ProfileStage(
                slug=stage_slug,
                node_name=stage_slug,
                next_stage_node="synthesis",
                prompt_file=f"{stage_slug}.md",
            ),
        ),
        reviewer_prompt_package="app.agents.market_entry.prompts",
        reviewer_prompt="reviewer.md",
        synthesis_prompt="synthesis.md",
        audit_prompt="audit.md",
    )


@pytest_asyncio.fixture
async def run_id() -> AsyncIterator[uuid.UUID]:
    async with AsyncSessionLocal() as session:
        run = Run(
            user_id=SINGLETON_USER_ID,
            task_id="market_entry",
            goal="Enter EU EV-charging market",
            status=RunStatus.running,
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        yield run.id


@pytest.mark.parametrize(
    "stage_slug",
    ["stage1_foundation", "stage2_competitive", "stage3_risk"],
)
@pytest.mark.asyncio
async def test_stage_node_persists_artifacts_and_evidence(
    run_id: uuid.UUID, stage_slug: str
) -> None:
    payload = {
        "artifacts": [
            {
                "path": f"{stage_slug}/findings.md",
                "content": "Top finding [^s1].",
                "kind": "markdown",
            }
        ],
        "evidence": [
            {
                "src_id": "s1",
                "title": "Source 1",
                "url": "https://example.com/1",
                "snippet": "Top finding snippet",
                "kind": "web",
                "provider": "tavily",
            }
        ],
        "summary": f"{stage_slug} pass complete",
    }
    fake = FakeChatModel(structured_responses=[payload])
    node = make_stage_node(stage_slug, model=fake, profile=_profile_without_workers(stage_slug))

    state: RunState = {
        "run_id": str(run_id),
        "goal": "x",
        "framing": {
            "objective": "obj",
            "target_market": "tm",
            "constraints": [],
            "questionnaire_answers": {},
        },
    }
    out = await node(state)

    assert out["artifacts"][f"{stage_slug}/findings.md"].startswith("Top finding")
    assert out["target_agents"] is None
    assert out["evidence"] == [
        {"src_id": "s1", "title": "Source 1", "url": "https://example.com/1"}
    ]

    async with AsyncSessionLocal() as session:
        artifact_rows = (
            (await session.execute(select(Artifact).where(Artifact.run_id == run_id)))
            .scalars()
            .all()
        )
        evidence_rows = (
            (await session.execute(select(Evidence).where(Evidence.run_id == run_id)))
            .scalars()
            .all()
        )
    assert len(artifact_rows) == 1
    assert artifact_rows[0].path == f"{stage_slug}/findings.md"
    assert len(evidence_rows) == 1
    assert evidence_rows[0].src_id == "s1"


@pytest.mark.asyncio
async def test_stage_node_reiterate_scope_passes_target_agents_to_prompt(
    run_id: uuid.UUID,
) -> None:
    payload = {
        "artifacts": [{"path": "stage2_competitive/pricing.md", "content": "Pricing [^p1]."}],
        "evidence": [{"src_id": "p1", "title": "Pricing src", "snippet": "x"}],
    }
    fake = FakeChatModel(structured_responses=[payload])
    node = make_stage_node(
        "stage2_competitive",
        model=fake,
        profile=_profile_without_workers("stage2_competitive"),
    )

    state: RunState = {
        "run_id": str(run_id),
        "goal": "x",
        "framing": {
            "objective": "o",
            "target_market": "t",
            "constraints": [],
            "questionnaire_answers": {},
        },
        "artifacts": {"stage2_competitive/competitor.md": "old"},
        "target_agents": ["pricing"],
    }
    await node(state)

    # Verify the model was prompted with the target_agents scope
    _, msgs = fake.structured_calls[0]
    flat = "\n".join(getattr(m, "content", "") for m in msgs)
    assert "pricing" in flat
    assert "Reiterate pass" in flat
    assert "at most three artifacts" in flat
    assert "400-900 words per artifact" in flat

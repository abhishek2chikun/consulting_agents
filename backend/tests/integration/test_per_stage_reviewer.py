"""Task 11: per-stage reviewer prompts and skill injection."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from langchain_core.messages import SystemMessage

from app.agents._engine.nodes.reviewer import make_reviewer_node
from app.agents._engine.profile import ConsultingProfile, ProfileStage
from app.agents.pricing import PRICING_PROFILE
from app.agents.profitability import PROFITABILITY_PROFILE
from app.core.db import AsyncSessionLocal
from app.models import SINGLETON_USER_ID, Run, RunStatus
from app.testing.fake_chat_model import FakeChatModel


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


def _profile(
    *,
    reviewer_prompt_for_stage: dict[str, str] | None = None,
    reviewer_skills_per_stage: dict[str, tuple[str, ...]] | None = None,
) -> ConsultingProfile:
    return ConsultingProfile(
        slug="test_review_profile",
        display_name="Test Review Profile",
        prompts_package="app.agents.market_entry.prompts",
        framing_prompt="framing.md",
        stages=(
            ProfileStage(
                slug="stage1_foundation",
                node_name="stage1_foundation",
                next_stage_node="synthesis",
                prompt_file="stage1_foundation.md",
            ),
        ),
        reviewer_prompt_package="app.agents.market_entry.prompts",
        reviewer_prompt="reviewer.md",
        synthesis_prompt="synthesis.md",
        audit_prompt="audit.md",
        reviewer_prompt_for_stage=reviewer_prompt_for_stage or {},
        reviewer_skills_per_stage=reviewer_skills_per_stage or {},
    )


def _fake() -> FakeChatModel:
    return FakeChatModel(
        structured_responses=[
            {
                "verdict": "advance",
                "stage": "stage1_foundation",
                "attempt": 1,
                "gaps": [],
                "target_agents": [],
                "rationale": "Complete.",
            }
        ]
    )


async def _invoke(run_id: uuid.UUID, fake: FakeChatModel, profile: ConsultingProfile) -> str:
    node = make_reviewer_node("stage1_foundation", model=fake, profile=profile)
    await node(
        {
            "run_id": str(run_id),
            "goal": "x",
            "stage_attempts": {"stage1_foundation": 1},
            "artifacts": {"stage1_foundation.md": "Fact [^src_id]."},
        }
    )
    messages = fake.structured_calls[0][1]
    system_message = messages[0]
    assert isinstance(system_message, SystemMessage)
    return str(system_message.content)


@pytest.mark.asyncio
async def test_reviewer_loads_stage_specific_prompt(run_id: uuid.UUID) -> None:
    fake = _fake()
    profile = _profile(
        reviewer_prompt_for_stage={"stage1_foundation": "reviewer_stage1_foundation.md"}
    )

    system_prompt = await _invoke(run_id, fake, profile)

    assert "Foundation-specific reviewer checks" in system_prompt


@pytest.mark.asyncio
async def test_reviewer_falls_back_to_shared_prompt(run_id: uuid.UUID) -> None:
    fake = _fake()

    system_prompt = await _invoke(run_id, fake, _profile())

    assert "# Reviewer — Strict Stage Critic" in system_prompt
    assert "Foundation-specific reviewer checks" not in system_prompt


@pytest.mark.asyncio
async def test_reviewer_injects_stage_skills(run_id: uuid.UUID) -> None:
    fake = _fake()
    profile = _profile(reviewer_skills_per_stage={"stage1_foundation": ("evidence-discipline",)})

    system_prompt = await _invoke(run_id, fake, profile)

    assert "## Applicable Consulting Skills" in system_prompt
    assert "Make every material claim traceable to reliable evidence" in system_prompt


def test_pricing_and_profitability_reviewers_use_own_prompt_packages() -> None:
    assert PRICING_PROFILE.reviewer_prompt_package == "app.agents.pricing.prompts"
    assert PROFITABILITY_PROFILE.reviewer_prompt_package == "app.agents.profitability.prompts"
    assert PRICING_PROFILE.load_prompt("reviewer") != PROFITABILITY_PROFILE.load_prompt("reviewer")

"""Integration test for M6.4 reviewer node."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.agents.market_entry.nodes.reviewer import make_reviewer_node
from app.agents.market_entry.state import RunState
from app.core.db import AsyncSessionLocal
from app.models import SINGLETON_USER_ID, Gate, Run, RunStatus
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


@pytest.mark.asyncio
async def test_reviewer_node_advance_writes_gate_and_state(
    run_id: uuid.UUID,
) -> None:
    fake = FakeChatModel(
        structured_responses=[
            {
                "verdict": "advance",
                "stage": "stage1_foundation",
                "attempt": 1,
                "gaps": [],
                "target_agents": [],
                "rationale": "All claims cited; objectives covered.",
            }
        ]
    )
    node = make_reviewer_node("stage1_foundation", model=fake)

    state: RunState = {
        "run_id": str(run_id),
        "goal": "x",
        "stage_attempts": {"stage1_foundation": 1},
        "artifacts": {"stage1/market.md": "Market is large [^s1]."},
    }
    out = await node(state)

    verdicts = out.get("gate_verdicts", {})
    assert verdicts["stage1_foundation"]["verdict"] == "advance"
    assert out.get("target_agents") in (None, [])

    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(Gate).where(Gate.run_id == run_id)
            )
        ).scalars().all()
    assert len(rows) == 1
    assert rows[0].stage == "stage1_foundation"
    assert rows[0].verdict == "advance"
    assert rows[0].attempt == 1


@pytest.mark.asyncio
async def test_reviewer_node_reiterate_sets_target_agents(
    run_id: uuid.UUID,
) -> None:
    fake = FakeChatModel(
        structured_responses=[
            {
                "verdict": "reiterate",
                "stage": "stage2_competitive",
                "attempt": 1,
                "gaps": ["Pricing missing for EU"],
                "target_agents": ["pricing"],
                "rationale": "Pricing analysis incomplete.",
            }
        ]
    )
    node = make_reviewer_node("stage2_competitive", model=fake)

    state: RunState = {
        "run_id": str(run_id),
        "goal": "x",
        "stage_attempts": {"stage2_competitive": 1},
        "artifacts": {},
    }
    out = await node(state)

    assert out["target_agents"] == ["pricing"]
    assert out["gate_verdicts"]["stage2_competitive"]["verdict"] == "reiterate"
    assert out["stage_attempts"]["stage2_competitive"] == 2

"""Integration test for M6.2 framing node."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.agents.market_entry.nodes.framing import build_framing_node
from app.agents.market_entry.state import RunState
from app.core.db import AsyncSessionLocal
from app.models import SINGLETON_USER_ID, Artifact, Run, RunStatus
from app.testing.fake_chat_model import FakeChatModel


@pytest_asyncio.fixture
async def run_id() -> AsyncIterator[uuid.UUID]:
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


@pytest.mark.asyncio
async def test_framing_node_writes_questionnaire_artifact_and_state(
    run_id: uuid.UUID,
) -> None:
    structured = {
        "brief": {
            "objective": "Assess EU EV-charging entry",
            "target_market": "EU, B2B fleet operators",
            "constraints": ["18-month horizon", "EUR 5M envelope"],
            "questionnaire_answers": {},
        },
        "questionnaire": {
            "items": [
                {
                    "id": "geography",
                    "label": "Target geography",
                    "type": "text",
                    "required": True,
                },
                {
                    "id": "horizon",
                    "label": "Time horizon",
                    "type": "select",
                    "options": ["6mo", "18mo", "3yr"],
                    "required": True,
                },
            ]
        },
    }
    fake = FakeChatModel(structured_responses=[structured])
    node = build_framing_node(model=fake)

    state: RunState = {
        "run_id": str(run_id),
        "goal": "Enter EU EV-charging market",
    }
    out = await node(state)

    # State updated with framing brief
    assert "framing" in out
    assert out["framing"]["objective"] == "Assess EU EV-charging entry"
    assert out["framing"]["target_market"] == "EU, B2B fleet operators"
    assert out["framing"]["constraints"] == ["18-month horizon", "EUR 5M envelope"]

    # Artifact persisted with questionnaire JSON
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(Artifact).where(
                    Artifact.run_id == run_id,
                    Artifact.path == "framing/questionnaire.json",
                )
            )
        ).scalars().all()
    assert len(rows) == 1
    payload = json.loads(rows[0].content)
    assert [it["id"] for it in payload["items"]] == ["geography", "horizon"]


@pytest.mark.asyncio
async def test_framing_node_invokes_model_with_goal_in_prompt(
    run_id: uuid.UUID,
) -> None:
    structured = {
        "brief": {
            "objective": "x",
            "target_market": "y",
            "constraints": [],
            "questionnaire_answers": {},
        },
        "questionnaire": {"items": []},
    }
    fake = FakeChatModel(structured_responses=[structured])
    node = build_framing_node(model=fake)

    state: RunState = {
        "run_id": str(run_id),
        "goal": "Launch saffron in Japan",
    }
    await node(state)

    # Verify model received the goal in its input
    assert len(fake.structured_calls) == 1
    _, msgs = fake.structured_calls[0]
    flat = json.dumps(
        [getattr(m, "content", str(m)) for m in (msgs if isinstance(msgs, list) else [msgs])]
    )
    assert "Launch saffron in Japan" in flat


def test_framing_node_is_callable_sync_for_graph_use() -> None:
    """LangGraph supports async nodes natively; verify the builder is callable."""
    fake = FakeChatModel()
    node = build_framing_node(model=fake)
    assert callable(node)
    # Don't actually invoke (no scripted response) — just confirm coroutine func
    assert asyncio.iscoroutinefunction(node)

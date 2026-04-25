"""Integration test for M6.9 audit node."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.agents.market_entry.nodes.audit import AUDIT_PATH, build_audit_node
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
            goal="x",
            status=RunStatus.running,
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        yield run.id


@pytest.mark.asyncio
async def test_audit_writes_audit_artifact_and_completes_run(
    run_id: uuid.UUID,
) -> None:
    fake = FakeChatModel(
        responses=[
            "## Weak Claims\n- none\n\n## Contradictions\n- none\n\n## Residual Gaps\n- none\n"
        ]
    )
    node = build_audit_node(model=fake)
    state: RunState = {
        "run_id": str(run_id),
        "goal": "x",
        "artifacts": {"final_report.md": "# Final\n- a [^s1]"},
        "gate_verdicts": {"stage1_foundation": {"verdict": "advance"}},  # type: ignore[typeddict-item]
    }

    out = await node(state)
    assert AUDIT_PATH in out["artifacts"]

    async with AsyncSessionLocal() as session:
        row = (
            await session.execute(
                select(Artifact).where(Artifact.run_id == run_id, Artifact.path == AUDIT_PATH)
            )
        ).scalar_one()
        run = await session.get(Run, run_id)
    assert "Weak Claims" in row.content
    assert run is not None
    assert run.status == RunStatus.completed

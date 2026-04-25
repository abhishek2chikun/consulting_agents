"""Integration test: run-lifecycle ORM tables round-trip (M5.1)."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.models import (
    SINGLETON_USER_ID,
    Artifact,
    Event,
    Evidence,
    EvidenceKind,
    Gate,
    Message,
    MessageRole,
    Run,
    RunStatus,
)


async def test_insert_run_message_event_artifact_gate_roundtrip() -> None:
    session = AsyncSessionLocal()
    run_id = uuid.uuid4()
    try:
        run = Run(
            id=run_id,
            user_id=SINGLETON_USER_ID,
            task_id="market_entry",
            goal="Validate market-entry viability for a new segment",
            status=RunStatus.created,
            model_snapshot={"max_stage_retries": 2},
        )
        session.add(run)
        await session.flush()

        session.add(
            Message(
                run_id=run_id,
                role=MessageRole.user,
                content="Start with market sizing assumptions.",
            )
        )
        session.add(
            Event(
                run_id=run_id,
                agent="framing",
                type="run_created",
                payload={"goal": run.goal},
            )
        )
        session.add(
            Artifact(
                run_id=run_id,
                path="framing/questionnaire.json",
                kind="json",
                content='{"items": []}',
            )
        )
        session.add(
            Gate(
                run_id=run_id,
                stage="stage_1_foundation",
                attempt=1,
                verdict="advance",
                gaps=[],
                target_agents=[],
                rationale="All required claims were cited.",
            )
        )
        session.add(
            Evidence(
                run_id=run_id,
                src_id="src_deadbeef",
                kind=EvidenceKind.web,
                url="https://example.com/source",
                chunk_id=None,
                title="Source title",
                snippet="Source snippet",
                provider="tavily",
            )
        )
        await session.commit()

        loaded_run = (await session.execute(select(Run).where(Run.id == run_id))).scalar_one()
        assert loaded_run.status == RunStatus.created
        assert loaded_run.task_id == "market_entry"

        loaded_messages = (
            await session.execute(select(Message).where(Message.run_id == run_id))
        ).scalars()
        assert len(list(loaded_messages)) == 1

        loaded_events = (
            await session.execute(select(Event).where(Event.run_id == run_id))
        ).scalars()
        assert len(list(loaded_events)) == 1

        loaded_artifacts = (
            await session.execute(select(Artifact).where(Artifact.run_id == run_id))
        ).scalars()
        assert len(list(loaded_artifacts)) == 1

        loaded_gates = (await session.execute(select(Gate).where(Gate.run_id == run_id))).scalars()
        assert len(list(loaded_gates)) == 1

        loaded_evidence = (
            await session.execute(select(Evidence).where(Evidence.run_id == run_id))
        ).scalars()
        assert len(list(loaded_evidence)) == 1
    finally:
        await session.execute(Run.__table__.delete().where(Run.id == run_id))
        await session.commit()
        await session.close()

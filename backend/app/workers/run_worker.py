"""Background run worker entrypoints (M5.5 framing skeleton)."""

from __future__ import annotations

import json
import uuid

from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.core.events import publish
from app.models import Artifact, Message, MessageRole, Run, RunStatus

QUESTIONNAIRE_PATH = "framing/questionnaire.json"
QUESTIONNAIRE_CONTENT = json.dumps(
    {
        "items": [
            {
                "id": "target_market",
                "label": "Target market",
                "type": "text",
                "required": True,
                "helper": "Specify geography + segment",
            },
            {
                "id": "time_horizon",
                "label": "Time horizon",
                "type": "text",
                "required": True,
            },
        ]
    }
)


async def start_framing(run_id: uuid.UUID) -> None:
    """Seed questionnaire artifact and publish artifact_update event."""
    async with AsyncSessionLocal() as session:
        run = await session.get(Run, run_id)
        if run is None:
            return

        existing = (
            await session.execute(
                select(Artifact).where(
                    Artifact.run_id == run_id,
                    Artifact.path == QUESTIONNAIRE_PATH,
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            session.add(
                Artifact(
                    run_id=run_id,
                    path=QUESTIONNAIRE_PATH,
                    kind="json",
                    content=QUESTIONNAIRE_CONTENT,
                )
            )
            await session.commit()

    await publish(run_id, "artifact_update", {"path": QUESTIONNAIRE_PATH}, agent="framing")


async def continue_after_framing(run_id: uuid.UUID, answers: dict[str, str]) -> None:
    """Persist answers and mark run as running."""
    async with AsyncSessionLocal() as session:
        run = await session.get(Run, run_id)
        if run is None:
            return
        run.status = RunStatus.running
        session.add(
            Message(
                run_id=run_id,
                role=MessageRole.user,
                content=json.dumps(answers),
            )
        )
        await session.commit()

    await publish(run_id, "answers_received", {"count": len(answers)}, agent="framing")


__all__ = ["continue_after_framing", "start_framing"]

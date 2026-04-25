"""M6.2 framing node.

Calls a chat model with structured output to produce a `FramingBrief`
and a `Questionnaire`, persists the questionnaire as the
``framing/questionnaire.json`` artifact, and emits an
``artifact_update`` SSE event so the frontend can render the
questionnaire form.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import select

from app.agents.market_entry.prompts import load as load_prompt
from app.agents.market_entry.state import RunState
from app.core.db import AsyncSessionLocal
from app.core.events import publish
from app.models import Artifact
from app.schemas.framing import FramingResponse

QUESTIONNAIRE_PATH = "framing/questionnaire.json"


def build_framing_node(
    *,
    model: object,
) -> Callable[[RunState], Awaitable[RunState]]:
    """Construct an async LangGraph node that runs the framing step."""

    system_prompt = load_prompt("framing")

    async def framing_node(state: RunState) -> RunState:
        goal = state.get("goal", "")
        document_ids = state.get("document_ids", []) or []
        user_msg = f"goal: {goal}\ndocument_ids: {document_ids}\n\nProduce the JSON object now."

        structured = model.with_structured_output(FramingResponse)  # type: ignore[attr-defined]
        result = await structured.ainvoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=user_msg)]
        )
        if not isinstance(result, FramingResponse):
            result = FramingResponse.model_validate(result)

        run_id = uuid.UUID(state["run_id"])
        questionnaire_json = result.questionnaire.model_dump_json()

        async with AsyncSessionLocal() as session:
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
                        content=questionnaire_json,
                    )
                )
            else:
                existing.content = questionnaire_json
            await session.commit()

        await publish(
            run_id,
            "artifact_update",
            {"path": QUESTIONNAIRE_PATH},
            agent="framing",
        )

        return {
            "framing": {
                "objective": result.brief.objective,
                "target_market": result.brief.target_market,
                "constraints": list(result.brief.constraints),
                "questionnaire_answers": dict(result.brief.questionnaire_answers),
            }
        }

    return framing_node


__all__ = ["QUESTIONNAIRE_PATH", "build_framing_node"]

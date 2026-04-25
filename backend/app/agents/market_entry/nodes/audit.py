"""M6.9 audit node — final auditor; marks the run completed."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import select

from app.agents.market_entry.prompts import load as load_prompt
from app.agents.market_entry.state import RunState
from app.core.db import AsyncSessionLocal
from app.core.events import publish
from app.models import Artifact, Run, RunStatus

AUDIT_PATH = "audit.md"


def build_audit_node(*, model: object) -> Callable[[RunState], Awaitable[RunState]]:
    system_prompt = load_prompt("audit")

    async def audit_node(state: RunState) -> RunState:
        run_uuid = uuid.UUID(state["run_id"])
        artifacts = dict(state.get("artifacts", {}) or {})
        gate_verdicts = state.get("gate_verdicts", {}) or {}

        report_body = artifacts.get("final_report.md", "(missing final_report.md)")
        user_msg = (
            f"final_report.md:\n{report_body}\n\n"
            f"gate_verdicts:\n{gate_verdicts}\n\n"
            "Produce audit.md now."
        )
        ai = await model.ainvoke(  # type: ignore[attr-defined]
            [SystemMessage(content=system_prompt), HumanMessage(content=user_msg)]
        )
        body = ai.content if hasattr(ai, "content") else str(ai)
        if not isinstance(body, str):
            body = str(body)

        async with AsyncSessionLocal() as session:
            row = (
                await session.execute(
                    select(Artifact).where(
                        Artifact.run_id == run_uuid,
                        Artifact.path == AUDIT_PATH,
                    )
                )
            ).scalar_one_or_none()
            if row is None:
                session.add(
                    Artifact(
                        run_id=run_uuid,
                        path=AUDIT_PATH,
                        kind="markdown",
                        content=body,
                    )
                )
            else:
                row.content = body

            run = await session.get(Run, run_uuid)
            if run is not None and run.status not in (
                RunStatus.cancelled,
                RunStatus.failed,
            ):
                run.status = RunStatus.completed
            await session.commit()

        await publish(
            run_uuid,
            "artifact_update",
            {"path": AUDIT_PATH},
            agent="audit",
        )
        await publish(run_uuid, "run_completed", {}, agent="audit")

        merged = dict(artifacts)
        merged[AUDIT_PATH] = body
        return {"artifacts": merged}

    return audit_node


__all__ = ["AUDIT_PATH", "build_audit_node"]

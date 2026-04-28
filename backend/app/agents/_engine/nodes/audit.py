"""M6.9 audit node - final auditor; marks the run completed."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import select

from app.agents._engine.paths import normalize_artifact_path
from app.agents._engine.profile import ConsultingProfile
from app.agents._engine.skills import inject_skills
from app.agents._engine.state import RunState
from app.core.db import AsyncSessionLocal
from app.core.events import publish
from app.models import Artifact, Run, RunStatus

AUDIT_PATH = "audit.md"
REPORT_PATH = "final_report.md"


def _default_profile() -> ConsultingProfile:
    from app.agents.market_entry.profile import MARKET_ENTRY_PROFILE

    return MARKET_ENTRY_PROFILE


def _get_artifact_by_path(artifacts: dict[str, str], expected_path: str) -> tuple[str, str]:
    if expected_path in artifacts:
        return expected_path, artifacts[expected_path]

    for path in sorted(normalize_artifact_path(expected_path) - {expected_path}):
        if path in artifacts:
            return path, artifacts[path]
    return expected_path, f"(missing {expected_path})"


def build_audit_node(
    *, model: object, profile: ConsultingProfile | None = None
) -> Callable[[RunState], Awaitable[RunState]]:
    profile = profile or _default_profile()
    system_prompt = inject_skills(profile.load_prompt("audit"), profile.audit_skills)

    async def audit_node(state: RunState) -> RunState:
        run_uuid = uuid.UUID(state["run_id"])
        artifacts = dict(state.get("artifacts", {}) or {})
        gate_verdicts = state.get("gate_verdicts", {}) or {}

        report_path, report_body = _get_artifact_by_path(artifacts, REPORT_PATH)
        user_msg = (
            f"{report_path}:\n{report_body}\n\n"
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
                run.completed_at = datetime.now(UTC)
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

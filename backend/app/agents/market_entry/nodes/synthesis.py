"""M6.8 synthesis node — final report assembly with citation validation."""

from __future__ import annotations

import re
import uuid
from collections.abc import Awaitable, Callable

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import select

from app.agents.market_entry.prompts import load as load_prompt
from app.agents.market_entry.state import RunState
from app.core.db import AsyncSessionLocal
from app.core.events import publish
from app.models import Artifact, Evidence

REPORT_PATH = "final_report.md"
CITATION_RE = re.compile(r"\[\^([^\]]+)\]")


class CitationError(ValueError):
    """Raised when the synthesised report cites an unknown ``src_id``."""


def _format_artifacts(artifacts: dict[str, str]) -> str:
    if not artifacts:
        return "(no artifacts)"
    return "\n\n".join(f"--- {p} ---\n{c}" for p, c in sorted(artifacts.items()))


def _format_evidence(rows: list[Evidence]) -> str:
    if not rows:
        return "(no evidence)"
    return "\n".join(f"[^{r.src_id}] {r.title} ({r.url or 'no-url'})" for r in rows)


def _render_sources(rows: list[Evidence]) -> str:
    if not rows:
        return ""
    lines = ["", "## Sources", ""]
    for r in sorted(rows, key=lambda x: x.src_id):
        url_part = f" — <{r.url}>" if r.url else ""
        lines.append(f"- `[^{r.src_id}]` {r.title}{url_part}")
    return "\n".join(lines)


def build_synthesis_node(*, model: object) -> Callable[[RunState], Awaitable[RunState]]:
    system_prompt = load_prompt("synthesis")

    async def synthesis_node(state: RunState) -> RunState:
        run_uuid = uuid.UUID(state["run_id"])
        framing = state.get("framing", {}) or {}
        artifacts = dict(state.get("artifacts", {}) or {})

        async with AsyncSessionLocal() as session:
            evidence_rows = list(
                (await session.execute(select(Evidence).where(Evidence.run_id == run_uuid)))
                .scalars()
                .all()
            )

        user_msg = (
            f"framing: {framing}\n\n"
            f"artifacts:\n{_format_artifacts(artifacts)}\n\n"
            f"available_evidence:\n{_format_evidence(evidence_rows)}\n\n"
            "Produce the final Markdown report now."
        )
        ai = await model.ainvoke(  # type: ignore[attr-defined]
            [SystemMessage(content=system_prompt), HumanMessage(content=user_msg)]
        )
        body = ai.content if hasattr(ai, "content") else str(ai)
        if not isinstance(body, str):
            body = str(body)

        # Validate every citation token resolves to a known src_id.
        cited = set(CITATION_RE.findall(body))
        known = {r.src_id for r in evidence_rows}
        unknown = cited - known
        if unknown:
            raise CitationError(f"synthesis cited unknown src_ids: {sorted(unknown)}")

        full_report = body.rstrip() + "\n" + _render_sources(evidence_rows) + "\n"

        async with AsyncSessionLocal() as session:
            row = (
                await session.execute(
                    select(Artifact).where(
                        Artifact.run_id == run_uuid,
                        Artifact.path == REPORT_PATH,
                    )
                )
            ).scalar_one_or_none()
            if row is None:
                session.add(
                    Artifact(
                        run_id=run_uuid,
                        path=REPORT_PATH,
                        kind="markdown",
                        content=full_report,
                    )
                )
            else:
                row.content = full_report
            await session.commit()

        await publish(
            run_uuid,
            "artifact_update",
            {"path": REPORT_PATH},
            agent="synthesis",
        )

        merged = dict(artifacts)
        merged[REPORT_PATH] = full_report
        return {"artifacts": merged}

    return synthesis_node


__all__ = ["CITATION_RE", "CitationError", "REPORT_PATH", "build_synthesis_node"]

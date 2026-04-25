"""M6.5–M6.7 stage research node builder.

For V1 the three "DeepAgent" stages (Foundation / Competitive / Risk)
share the same orchestration shape: load a stage system prompt, give
the model the framing brief + accumulated artifacts + the optional
``target_agents`` scope (when this is a reiterate pass), and ask it to
produce a list of artifact files. Each file is persisted via
``write_artifact`` (which also publishes ``artifact_update`` events)
and returned in the merged ``RunState.artifacts`` map.

The ``tools`` parameter is accepted for forward-compatibility with a
real DeepAgent ReAct loop in M7+. For V1 we use structured output so
the workflow is deterministic and testable with a scripted model.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.agents.market_entry.prompts import load as load_prompt
from app.agents.market_entry.state import EvidenceRef, RunState
from app.core.db import AsyncSessionLocal
from app.core.events import publish
from app.models import Artifact, Evidence, EvidenceKind


class ArtifactFile(BaseModel):
    path: str
    content: str
    kind: Literal["markdown", "json", "txt"] = "markdown"


class EvidenceCitation(BaseModel):
    src_id: str
    title: str
    url: str | None = None
    snippet: str = ""
    kind: Literal["web", "doc"] = "web"
    provider: str = "stage_node"


class StageOutput(BaseModel):
    """Structured output for one stage pass.

    The model returns a list of artifact files plus the evidence rows
    that back the citations referenced inside those files.
    """

    artifacts: list[ArtifactFile] = Field(default_factory=list)
    evidence: list[EvidenceCitation] = Field(default_factory=list)
    summary: str = ""


def _format_existing(artifacts: dict[str, str]) -> str:
    if not artifacts:
        return "(no prior artifacts)"
    lines = []
    for p, c in sorted(artifacts.items()):
        snippet = c if len(c) <= 400 else c[:400] + "…"
        lines.append(f"--- {p} ---\n{snippet}")
    return "\n\n".join(lines)


def make_stage_node(
    stage_slug: str,
    *,
    model: object,
    tools: list[object] | None = None,  # noqa: ARG001  # reserved for M7 DeepAgent wiring
) -> Callable[[RunState], Awaitable[RunState]]:
    """Build an async LangGraph node for a stage.

    ``stage_slug`` must match a top-level prompt file
    (e.g. ``"stage1_foundation"``).
    """

    system_prompt = load_prompt(stage_slug)

    async def stage_node(state: RunState) -> RunState:
        framing = state.get("framing", {}) or {}
        target_agents = state.get("target_agents") or []
        existing = dict(state.get("artifacts", {}) or {})

        scope_clause = (
            f"Reiterate pass — focus only on these sub-agents: {target_agents}.\n"
            if target_agents
            else "First pass — cover the full stage scope.\n"
        )

        user_msg = (
            f"stage: {stage_slug}\n"
            f"framing: {framing}\n"
            f"{scope_clause}"
            f"existing_artifacts:\n{_format_existing(existing)}\n\n"
            "Produce a StageOutput object with artifacts (each citing "
            "evidence via [^src_id] tokens) and a matching evidence list."
        )

        structured = model.with_structured_output(StageOutput)  # type: ignore[attr-defined]
        result = await structured.ainvoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=user_msg)]
        )
        if not isinstance(result, StageOutput):
            result = StageOutput.model_validate(result)

        run_uuid = uuid.UUID(state["run_id"])
        merged = dict(existing)

        async with AsyncSessionLocal() as session:
            for af in result.artifacts:
                merged[af.path] = af.content
                row = (
                    await session.execute(
                        select(Artifact).where(
                            Artifact.run_id == run_uuid,
                            Artifact.path == af.path,
                        )
                    )
                ).scalar_one_or_none()
                if row is None:
                    session.add(
                        Artifact(
                            run_id=run_uuid,
                            path=af.path,
                            kind=af.kind,
                            content=af.content,
                        )
                    )
                else:
                    row.content = af.content
                    row.kind = af.kind

            for ev in result.evidence:
                exists = (
                    await session.execute(
                        select(Evidence).where(
                            Evidence.run_id == run_uuid,
                            Evidence.src_id == ev.src_id,
                        )
                    )
                ).scalar_one_or_none()
                if exists is None:
                    session.add(
                        Evidence(
                            run_id=run_uuid,
                            src_id=ev.src_id,
                            title=ev.title,
                            url=ev.url,
                            snippet=ev.snippet or ev.title,
                            kind=EvidenceKind(ev.kind),
                            provider=ev.provider,
                        )
                    )
            await session.commit()

        # Emit artifact_update events after commit so subscribers can
        # safely fetch the persisted content.
        for af in result.artifacts:
            await publish(
                run_uuid,
                "artifact_update",
                {"path": af.path},
                agent=stage_slug,
            )
        if result.summary:
            await publish(
                run_uuid,
                "agent_message",
                {"text": result.summary},
                agent=stage_slug,
            )

        evidence_state = list(state.get("evidence", []) or [])
        existing_ids = {e["src_id"] for e in evidence_state}
        for ev in result.evidence:
            if ev.src_id not in existing_ids:
                ref: EvidenceRef = {"src_id": ev.src_id, "title": ev.title}
                if ev.url:
                    ref["url"] = ev.url
                evidence_state.append(ref)

        return {
            "artifacts": merged,
            "evidence": evidence_state,
            # Clear target_agents after the reiterate pass consumes it
            "target_agents": None,
        }

    return stage_node


__all__ = ["ArtifactFile", "EvidenceCitation", "StageOutput", "make_stage_node"]

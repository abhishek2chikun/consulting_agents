"""M6.8 synthesis node - final report assembly with citation validation."""

from __future__ import annotations

import re
import uuid
from collections.abc import Awaitable, Callable

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import select

from app.agents._engine.profile import ConsultingProfile
from app.agents._engine.state import RunState
from app.core.db import AsyncSessionLocal
from app.core.events import publish
from app.models import Artifact, Evidence

REPORT_PATH = "final_report.md"
CITATION_RE = re.compile(r"\[\^([^\]]+)\]")


class CitationError(ValueError):
    """Raised when the synthesised report cites an unknown ``src_id``."""


def _default_profile() -> ConsultingProfile:
    from app.agents.market_entry.profile import MARKET_ENTRY_PROFILE

    return MARKET_ENTRY_PROFILE


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


def build_synthesis_node(
    *, model: object, profile: ConsultingProfile | None = None
) -> Callable[[RunState], Awaitable[RunState]]:
    profile = profile or _default_profile()
    system_prompt = profile.load_prompt("synthesis")

    # Bounded self-heal: if the model invents citations, give it a
    # second (and third) chance with the unknowns spelled out, then
    # fall back to stripping bad tokens rather than failing the run.
    max_attempts = 3

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

        known = {r.src_id for r in evidence_rows}
        allowlist_block = ", ".join(f"[^{sid}]" for sid in sorted(known)) if known else "(none)"

        base_user_msg = (
            f"framing: {framing}\n\n"
            f"artifacts:\n{_format_artifacts(artifacts)}\n\n"
            f"available_evidence:\n{_format_evidence(evidence_rows)}\n\n"
            "ALLOWED CITATION TOKENS — copy verbatim, do not invent any others:\n"
            f"{allowlist_block}\n\n"
            "Produce the final Markdown report now. Every [^src_id] token must "
            "appear in the allowed list above; cite only what the evidence supports."
        )

        body = ""
        unknown: set[str] = set()
        attempt = 0
        while attempt < max_attempts:
            attempt += 1
            if attempt == 1:
                user_msg = base_user_msg
            else:
                user_msg = (
                    base_user_msg + "\n\n---\nPREVIOUS DRAFT REJECTED.\n"
                    f"These citation tokens are not in the allowed list and must be "
                    f"removed or replaced: {sorted(unknown)}.\n"
                    "Re-emit the FULL Markdown report. Use ONLY tokens from the "
                    "ALLOWED CITATION TOKENS list. If a claim has no supporting "
                    "evidence, drop the citation (and soften or remove the claim) "
                    "rather than inventing a src_id."
                )
            ai = await model.ainvoke(  # type: ignore[attr-defined]
                [SystemMessage(content=system_prompt), HumanMessage(content=user_msg)]
            )
            body = ai.content if hasattr(ai, "content") else str(ai)
            if not isinstance(body, str):
                body = str(body)

            cited = set(CITATION_RE.findall(body))
            unknown = cited - known
            if not unknown:
                break

            await publish(
                run_uuid,
                "agent_message",
                {
                    "text": (
                        f"Synthesis self-heal attempt {attempt}/{max_attempts}: "
                        f"{len(unknown)} unknown citation(s) detected, retrying."
                    )
                },
                agent="synthesis",
            )

        # Final guard: if the model still cited unknown ids after all
        # attempts, strip the bad tokens rather than crashing the run.
        # This keeps the report shippable and surfaces the issue via
        # an event the UI can render.
        if unknown:
            for bad in unknown:
                body = body.replace(f"[^{bad}]", "")
            # Collapse the artefacts of stripped tokens (double spaces, " .")
            body = re.sub(r" +([.,;:!?])", r"\1", body)
            body = re.sub(r" {2,}", " ", body)
            await publish(
                run_uuid,
                "agent_message",
                {
                    "text": (
                        "Synthesis: stripped "
                        f"{len(unknown)} fabricated citation(s) after "
                        f"{max_attempts} attempts: {sorted(unknown)[:8]}"
                        + ("…" if len(unknown) > 8 else "")
                    )
                },
                agent="synthesis",
            )

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

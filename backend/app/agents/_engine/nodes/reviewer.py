"""M6.4 reviewer node - gate decisions per stage.

The reviewer reads the current artifacts and the framing brief, calls
the model with structured output, persists a `Gate` row, publishes a
`gate_verdict` SSE event, and returns a state update including the
verdict, an incremented `stage_attempts[stage]` (when reiterating),
and the `target_agents` list (used by the conditional edges in M6.10
to scope the next pass).
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents._engine.profile import ConsultingProfile
from app.agents._engine.skills import inject_skills
from app.agents._engine.state import RunState
from app.core.db import AsyncSessionLocal
from app.core.events import publish
from app.models import Gate
from app.schemas.reviewer import GateVerdictModel


def _default_profile() -> ConsultingProfile:
    from app.agents.market_entry.profile import MARKET_ENTRY_PROFILE

    return MARKET_ENTRY_PROFILE


def _format_artifacts(artifacts: dict[str, str]) -> str:
    if not artifacts:
        return "(no artifacts produced yet)"
    parts = []
    for path, body in sorted(artifacts.items()):
        parts.append(f"--- {path} ---\n{body}")
    return "\n\n".join(parts)


def make_reviewer_node(
    stage_slug: str,
    *,
    model: object,
    profile: ConsultingProfile | None = None,
) -> Callable[[RunState], Awaitable[RunState]]:
    """Return an async LangGraph node that reviews ``stage_slug``."""

    profile = profile or _default_profile()
    system_prompt = profile.load_prompt("reviewer")
    reviewer_prompt_file = profile.reviewer_prompt_for_stage.get(stage_slug)
    if reviewer_prompt_file:
        stage_prompt = profile._read(profile.reviewer_prompt_package, reviewer_prompt_file)
        system_prompt = f"{system_prompt}\n\n{stage_prompt}"
    system_prompt = inject_skills(
        system_prompt,
        profile.reviewer_skills_per_stage.get(stage_slug, ()),
    )

    async def reviewer_node(state: RunState) -> RunState:
        attempts = dict(state.get("stage_attempts", {}) or {})
        attempt = attempts.get(stage_slug, 1)
        artifacts = state.get("artifacts", {}) or {}
        framing = state.get("framing", {}) or {}

        user_msg = (
            f"stage: {stage_slug}\n"
            f"attempt: {attempt}\n"
            f"framing: {framing}\n\n"
            f"artifacts:\n{_format_artifacts(dict(artifacts))}\n\n"
            "Issue your GateVerdict JSON now."
        )

        structured = model.with_structured_output(GateVerdictModel)  # type: ignore[attr-defined]
        verdict_model = await structured.ainvoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=user_msg)]
        )
        if not isinstance(verdict_model, GateVerdictModel):
            verdict_model = GateVerdictModel.model_validate(verdict_model)

        # Force stage_slug + attempt to authoritative coordinator values
        # (model may echo them but we don't trust those fields).
        verdict_model = verdict_model.model_copy(update={"stage": stage_slug, "attempt": attempt})

        run_uuid = uuid.UUID(state["run_id"])
        async with AsyncSessionLocal() as session:
            session.add(
                Gate(
                    run_id=run_uuid,
                    stage=stage_slug,
                    attempt=attempt,
                    verdict=verdict_model.verdict,
                    gaps=list(verdict_model.gaps),
                    target_agents=list(verdict_model.target_agents),
                    rationale=verdict_model.rationale,
                )
            )
            await session.commit()

        await publish(
            run_uuid,
            "gate_verdict",
            {
                "stage": stage_slug,
                "attempt": attempt,
                "verdict": verdict_model.verdict,
                "target_agents": list(verdict_model.target_agents),
                "gaps": list(verdict_model.gaps),
            },
            agent="reviewer",
        )

        gate_verdicts = dict(state.get("gate_verdicts", {}) or {})
        gate_verdicts[stage_slug] = {
            "verdict": verdict_model.verdict,
            "stage": stage_slug,
            "attempt": attempt,
            "gaps": list(verdict_model.gaps),
            "target_agents": list(verdict_model.target_agents),
            "rationale": verdict_model.rationale,
        }

        update: RunState = {
            "gate_verdicts": gate_verdicts,
            "target_agents": list(verdict_model.target_agents) or None,
        }
        if verdict_model.verdict == "reiterate":
            attempts[stage_slug] = attempt + 1
            update["stage_attempts"] = attempts

        return update

    return reviewer_node


__all__ = ["make_reviewer_node"]

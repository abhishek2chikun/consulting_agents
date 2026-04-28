"""M6.5-M6.7 stage research node builder.

For V1 the three "DeepAgent" stages (Foundation / Competitive / Risk)
share the same orchestration shape: load a stage system prompt, give
the model the framing brief + accumulated artifacts + the optional
``target_agents`` scope (when this is a reiterate pass), and ask it to
produce a list of artifact files. Each file is persisted via
``write_artifact`` (which also publishes ``artifact_update`` events)
and returned in the merged ``RunState.artifacts`` map.

    When tools are provided, the stage first runs a bounded ReAct loop and
    then asks the model to produce the same structured output used by the
    no-tools fallback path.
"""

from __future__ import annotations

import inspect
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, Literal, cast

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.agents._engine.profile import ConsultingProfile
from app.agents._engine.skills import inject_skills
from app.agents._engine.state import EvidenceRef, RunState
from app.core.config import get_settings
from app.core.db import AsyncSessionLocal
from app.core.events import publish
from app.models import Artifact, Evidence, EvidenceKind


class ArtifactFile(BaseModel):
    path: str
    content: str = Field(
        description="Concise Markdown artifact content, ideally 400-900 words.",
    )
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

    artifacts: list[ArtifactFile] = Field(
        default_factory=list,
        description="One to three concise artifacts for this stage.",
    )
    evidence: list[EvidenceCitation] = Field(
        default_factory=list,
        description="Three to eight evidence rows cited by artifact content.",
    )
    summary: str = ""


def _default_profile() -> ConsultingProfile:
    from app.agents.market_entry.profile import MARKET_ENTRY_PROFILE

    return MARKET_ENTRY_PROFILE


def _format_existing(artifacts: dict[str, str]) -> str:
    if not artifacts:
        return "(no prior artifacts)"
    lines = []
    for p, c in sorted(artifacts.items()):
        snippet = c if len(c) <= 400 else c[:400] + "…"
        lines.append(f"--- {p} ---\n{snippet}")
    return "\n\n".join(lines)


def _stage_required_skills(profile: ConsultingProfile, stage_slug: str) -> tuple[str, ...]:
    for stage in profile.stages:
        if stage.slug == stage_slug or stage.node_name == stage_slug:
            return stage.required_skills
    return ()


def _tool_name(tool: object) -> str | None:
    name = getattr(tool, "name", None)
    return name if isinstance(name, str) else None


def _safe_bind_tools(model: object, tools: list[object]) -> object:
    if not hasattr(model, "bind_tools"):
        return model
    try:
        return cast(Any, model).bind_tools(tools)
    except NotImplementedError:
        return model


def _normalize_tool_call(call: object, index: int) -> tuple[str | None, str, object]:
    if isinstance(call, dict):
        raw_name = call.get("name")
        raw_id = call.get("id")
        args = call.get("args") or {}
    else:
        raw_name = getattr(call, "name", None)
        raw_id = getattr(call, "id", None)
        args = getattr(call, "args", None) or {}

    name = raw_name if isinstance(raw_name, str) and raw_name else None
    tool_call_id = raw_id if isinstance(raw_id, str) and raw_id else f"malformed_tool_call_{index}"
    return name, tool_call_id, args


async def _invoke_tool(tool: object, args: object) -> object:
    if hasattr(tool, "ainvoke"):
        return await cast(Any, tool).ainvoke(args)
    if hasattr(tool, "invoke"):
        result = cast(Any, tool).invoke(args)
    elif callable(tool):
        result = tool(args)
    else:
        raise TypeError(f"Tool {tool!r} is not invokable")
    if inspect.isawaitable(result):
        return await result
    return result


def make_stage_node(
    stage_slug: str,
    *,
    model: object,
    tools: list[object] | None = None,
    profile: ConsultingProfile | None = None,
) -> Callable[[RunState], Awaitable[RunState]]:
    """Build an async LangGraph node for a stage.

    ``stage_slug`` must match a top-level prompt file
    (e.g. ``"stage1_foundation"``).
    """

    profile = profile or _default_profile()
    system_prompt = inject_skills(
        profile.load_prompt(stage_slug),
        _stage_required_skills(profile, stage_slug),
    )
    available_tools = list(tools or [])

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
            "evidence via [^src_id] tokens) and a matching evidence list. "
            "Keep the response compact enough for one provider call: at most "
            "three artifacts, 400-900 words per artifact, and only the most "
            "decision-relevant evidence rows. Return valid JSON only."
        )

        messages: list[BaseMessage] = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_msg),
        ]
        executed_tool_calls = 0

        if available_tools:
            loop_model = _safe_bind_tools(model, available_tools)
            tools_by_name = {name: tool for tool in available_tools if (name := _tool_name(tool))}
            for _ in range(get_settings().react_max_iterations):
                ai = await cast(Any, loop_model).ainvoke(messages)
                if not isinstance(ai, AIMessage):
                    ai = AIMessage(content=getattr(ai, "content", str(ai)))
                messages.append(ai)
                tool_calls = ai.tool_calls or []
                if not tool_calls:
                    break
                for index, call in enumerate(tool_calls):
                    name, tool_call_id, args = _normalize_tool_call(call, index)
                    if name is None:
                        messages.append(
                            ToolMessage(
                                content="Malformed tool call: missing tool name",
                                tool_call_id=tool_call_id,
                            )
                        )
                        continue
                    tool = tools_by_name.get(name)
                    if tool is None:
                        content = f"Tool not found: {name}"
                    else:
                        executed_tool_calls += 1
                        try:
                            content = str(await _invoke_tool(tool, args))
                        except Exception as exc:
                            content = (
                                f"Tool execution failed for {name}: {type(exc).__name__}: {exc}"
                            )
                    messages.append(
                        ToolMessage(
                            content=content,
                            tool_call_id=tool_call_id,
                            name=name,
                        )
                    )

        structured_messages = messages
        if available_tools:
            structured_messages = [
                *messages,
                HumanMessage(content="Now produce StageOutput"),
            ]

        structured = model.with_structured_output(StageOutput)  # type: ignore[attr-defined]
        result = await structured.ainvoke(structured_messages)
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
        if available_tools and executed_tool_calls == 0:
            await publish(
                run_uuid,
                "agent_message",
                {"text": f"{stage_slug}: produced StageOutput without tool use"},
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

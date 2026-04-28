"""Shared scripted smoke-test helpers for V1.6 profile wiring."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from sqlalchemy import delete, select

from app.core.db import AsyncSessionLocal
from app.models import SINGLETON_USER_ID, Artifact, Event, Gate, Run, RunStatus
from app.testing.fake_chat_model import FakeChatModel


def agent_id_from_messages(messages: Sequence[BaseMessage]) -> str:
    for message in messages:
        if isinstance(message, HumanMessage):
            content = str(message.content)
            for line in content.splitlines():
                if line.startswith("stage: "):
                    return line.removeprefix("stage: ")
    raise AssertionError("missing stage line")


class ScriptedResearchModel(FakeChatModel):
    def __init__(
        self,
        *,
        tool_calls_by_agent: dict[str, list[dict[str, Any]]],
        structured_responses_by_agent: dict[str, dict[str, Any]],
    ) -> None:
        super().__init__()
        object.__setattr__(self, "tool_calls_by_agent", dict(tool_calls_by_agent))
        object.__setattr__(
            self,
            "structured_responses_by_agent",
            dict(structured_responses_by_agent),
        )
        object.__setattr__(self, "response_counts", {})

    def _generate(  # type: ignore[override]
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> Any:
        self.calls.append(messages)
        agent_id = agent_id_from_messages(messages)
        counts = dict(self.response_counts)
        count = counts.get(agent_id, 0)
        counts[agent_id] = count + 1
        object.__setattr__(self, "response_counts", counts)

        scripted_calls = self.tool_calls_by_agent.get(agent_id, [])
        if count < len(scripted_calls):
            tool_call = scripted_calls[count]
            ai = AIMessage(
                content=f"Use {tool_call['name']} for {agent_id}",
                tool_calls=[tool_call],
            )
        else:
            ai = AIMessage(content=f"Ready to finalize {agent_id}")

        from langchain_core.outputs import ChatGeneration, ChatResult

        return ChatResult(generations=[ChatGeneration(message=ai)])

    def with_structured_output(self, schema: type[Any] | None = None, **_: Any) -> Any:  # type: ignore[override]
        return _StructuredByAgentRunnable(self, schema)

    def bind_tools(self, tools: Sequence[object], **_: Any) -> ScriptedResearchModel:  # type: ignore[override]
        object.__setattr__(self, "bound_tools", list(tools))
        return self


class _StructuredByAgentRunnable:
    def __init__(self, parent: ScriptedResearchModel, schema: type[Any] | None) -> None:
        self._parent = parent
        self._schema = schema

    async def ainvoke(self, messages: Sequence[BaseMessage], **_: Any) -> Any:
        self._parent.structured_calls.append((self._schema, messages))
        agent_id = agent_id_from_messages(messages)
        payload = self._parent.structured_responses_by_agent[agent_id]
        if self._schema is None:
            return payload
        return self._schema.model_validate(payload)


class RecordingTool:
    def __init__(self, name: str) -> None:
        self.name = name
        self.calls: list[dict[str, Any]] = []

    async def ainvoke(self, args: Any) -> str:
        payload = dict(args or {})
        self.calls.append(payload)
        return f"{self.name} result for {payload.get('query', '')}"


@dataclass(frozen=True)
class ProfileSmokeSpec:
    task_type: str
    goal: str
    answer_key: str
    answer_value: str
    framing_response: dict[str, Any]
    stage_slugs: tuple[str, ...]
    workers_by_stage: dict[str, tuple[str, ...]]
    stage_required_skill_titles: dict[str, tuple[str, ...]]
    reviewer_skill_titles: dict[str, tuple[str, ...]]
    framing_skill_titles: tuple[str, ...]
    synthesis_skill_titles: tuple[str, ...]
    audit_skill_titles: tuple[str, ...]
    tool_agents: tuple[str, ...]
    final_report_heading: str


def build_stage_payloads(spec: ProfileSmokeSpec) -> dict[str, dict[str, Any]]:
    payloads: dict[str, dict[str, Any]] = {}
    ordinal = 1
    for stage_slug in spec.stage_slugs:
        for worker_slug in spec.workers_by_stage[stage_slug]:
            agent_id = f"{stage_slug}.{worker_slug}"
            src_id = f"{worker_slug}_{ordinal}"
            payloads[agent_id] = {
                "artifacts": [
                    {
                        "path": f"analysis_{ordinal}.md",
                        "content": f"{agent_id} finding {ordinal} [^{src_id}].",
                        "kind": "markdown",
                    },
                    {
                        "path": f"supporting_{ordinal}.md",
                        "content": f"{agent_id} support {ordinal} [^{src_id}].",
                        "kind": "markdown",
                    },
                ],
                "evidence": [
                    {
                        "src_id": src_id,
                        "title": f"{agent_id} source {ordinal}",
                        "url": f"https://example.com/{src_id}",
                        "snippet": f"Snippet for {agent_id}",
                        "kind": "web",
                        "provider": "fake_tool",
                    }
                ],
                "summary": f"{agent_id} summary {ordinal}",
            }
            ordinal += 1
    return payloads


def build_final_report(spec: ProfileSmokeSpec) -> str:
    lines = [f"# {spec.final_report_heading}", "", "## Executive Summary"]
    for index, stage_slug in enumerate(spec.stage_slugs, start=1):
        first_worker = spec.workers_by_stage[stage_slug][0]
        lines.append(f"- {stage_slug} synthesized using [^{first_worker}_{index * 3 - 2}].")
    return "\n".join(lines) + "\n"


def build_research_model(spec: ProfileSmokeSpec) -> ScriptedResearchModel:
    tool_calls_by_agent = {
        agent_id: [
            {
                "name": "web_search",
                "args": {
                    "query": f"{agent_id} market evidence",
                    "agent_id": agent_id,
                },
                "id": f"call_{agent_id.replace('.', '_')}",
            }
        ]
        for agent_id in spec.tool_agents
    }
    return ScriptedResearchModel(
        tool_calls_by_agent=tool_calls_by_agent,
        structured_responses_by_agent=build_stage_payloads(spec),
    )


def build_models(spec: ProfileSmokeSpec) -> dict[str, FakeChatModel]:
    return {
        "framing": FakeChatModel(structured_responses=[spec.framing_response]),
        "research": build_research_model(spec),
        "reviewer": FakeChatModel(
            structured_responses=[
                {
                    "verdict": "advance",
                    "stage": stage_slug,
                    "attempt": 1,
                    "gaps": [],
                    "target_agents": [],
                    "rationale": f"{stage_slug} passes review",
                }
                for stage_slug in spec.stage_slugs
            ]
        ),
        "synthesis": FakeChatModel(responses=[build_final_report(spec)]),
        "audit": FakeChatModel(
            responses=[
                "## Weak Claims\n- none\n## Contradictions\n- none\n## Residual Gaps\n- none\n"
            ]
        ),
    }


async def create_run(*, task_type: str, goal: str) -> uuid.UUID:
    async with AsyncSessionLocal() as session:
        run = Run(
            user_id=SINGLETON_USER_ID,
            task_id=task_type,
            goal=goal,
            status=RunStatus.questioning,
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        return run.id


async def cleanup_run(run_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(delete(Run).where(Run.id == run_id))
        await session.commit()


async def artifact_content(run_id: uuid.UUID, path: str) -> str:
    async with AsyncSessionLocal() as session:
        row = (
            await session.execute(
                select(Artifact.content).where(Artifact.run_id == run_id, Artifact.path == path)
            )
        ).scalar_one()
    return str(row)


def system_prompt_text(model: FakeChatModel, *, structured: bool) -> str:
    calls = model.structured_calls if structured else model.calls
    messages = calls[0][1] if structured else calls[0]
    system_message = next(message for message in messages if isinstance(message, SystemMessage))
    return str(system_message.content)


async def run_summary(run_id: uuid.UUID) -> tuple[set[str], list[Gate], list[Event]]:
    async with AsyncSessionLocal() as session:
        artifact_paths = {
            row.path
            for row in (await session.execute(select(Artifact).where(Artifact.run_id == run_id)))
            .scalars()
            .all()
        }
        gate_rows = (
            (await session.execute(select(Gate).where(Gate.run_id == run_id))).scalars().all()
        )
        event_rows = (
            (await session.execute(select(Event).where(Event.run_id == run_id))).scalars().all()
        )
    return artifact_paths, list(gate_rows), list(event_rows)


__all__ = [
    "ProfileSmokeSpec",
    "RecordingTool",
    "ScriptedResearchModel",
    "agent_id_from_messages",
    "artifact_content",
    "build_models",
    "build_final_report",
    "cleanup_run",
    "create_run",
    "run_summary",
    "system_prompt_text",
]

"""Integration tests for stage worker fanout."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator, Sequence
from typing import Any

import pytest
import pytest_asyncio
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from sqlalchemy import select

from app.agents._engine.profile import ConsultingProfile, ProfileStage, WorkerSpec
from app.agents.market_entry.nodes.stage import make_stage_node
from app.agents.market_entry.state import RunState
from app.core.config import get_settings
from app.core.db import AsyncSessionLocal
from app.models import SINGLETON_USER_ID, Artifact, Event, Run, RunStatus
from app.testing.fake_chat_model import FakeChatModel


class RecordingFakeChatModel(FakeChatModel):
    def __init__(self, *, structured_responses: dict[str, dict[str, Any]]) -> None:
        super().__init__()
        self._structured_by_agent = structured_responses

    def with_structured_output(self, schema: type[Any] | None = None, **_: Any) -> Any:  # type: ignore[override]
        return _AgentStructuredRunnable(self, schema)


class _AgentStructuredRunnable:
    def __init__(self, parent: RecordingFakeChatModel, schema: type[Any] | None) -> None:
        self._parent = parent
        self._schema = schema

    async def ainvoke(self, messages: Sequence[BaseMessage], **_: Any) -> Any:
        self._parent.structured_calls.append((self._schema, messages))
        agent_id = _agent_id_from_messages(messages)
        payload = self._parent._structured_by_agent[agent_id]
        if self._schema is None:
            return payload
        return self._schema.model_validate(payload)


class GateStructuredRunnable:
    def __init__(self, parent: GateFakeChatModel, schema: type[Any] | None) -> None:
        self._parent = parent
        self._schema = schema

    async def ainvoke(self, messages: Sequence[BaseMessage], **_: Any) -> Any:
        agent_id = _agent_id_from_messages(messages)
        await self._parent.enter(agent_id)
        payload = {
            "artifacts": [
                {
                    "path": "findings.md",
                    "content": f"{agent_id} finding [^{agent_id.rsplit('.', 1)[1]}-src].",
                }
            ],
            "evidence": [
                {"src_id": f"{agent_id.rsplit('.', 1)[1]}-src", "title": f"Source {agent_id}"}
            ],
            "summary": f"{agent_id} complete",
        }
        if self._schema is None:
            return payload
        return self._schema.model_validate(payload)


class GateFakeChatModel(FakeChatModel):
    def __init__(self) -> None:
        super().__init__()
        object.__setattr__(self, "active", 0)
        object.__setattr__(self, "max_active", 0)
        object.__setattr__(self, "started", [])
        object.__setattr__(self, "finished", [])

    def with_structured_output(self, schema: type[Any] | None = None, **_: Any) -> Any:  # type: ignore[override]
        return GateStructuredRunnable(self, schema)

    async def enter(self, agent_id: str) -> None:
        object.__setattr__(self, "active", self.active + 1)
        object.__setattr__(self, "max_active", max(self.max_active, self.active))
        self.started.append(agent_id)
        await asyncio.sleep(0.01)
        self.finished.append(agent_id)
        object.__setattr__(self, "active", self.active - 1)


class RecordingTool:
    def __init__(self, name: str) -> None:
        self.name = name
        self.calls: list[Any] = []

    async def ainvoke(self, args: Any) -> str:
        self.calls.append(args)
        return f"{self.name} result"


@pytest_asyncio.fixture
async def run_id() -> AsyncIterator[uuid.UUID]:
    async with AsyncSessionLocal() as session:
        run = Run(
            user_id=SINGLETON_USER_ID,
            task_id="market_entry",
            goal="Enter EU EV-charging market",
            status=RunStatus.running,
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        yield run.id


def _profile(*, workers: tuple[WorkerSpec, ...]) -> ConsultingProfile:
    return ConsultingProfile(
        slug="test_profile",
        display_name="Test Profile",
        prompts_package="app.agents.market_entry.prompts",
        framing_prompt="framing.md",
        stages=(
            ProfileStage(
                slug="stage1_foundation",
                node_name="stage1_foundation",
                next_stage_node="synthesis",
                prompt_file="stage1_foundation.md",
                required_skills=("evidence-discipline",),
                workers=workers,
            ),
        ),
        reviewer_prompt_package="app.agents.market_entry.prompts",
        reviewer_prompt="reviewer.md",
        synthesis_prompt="synthesis.md",
        audit_prompt="audit.md",
    )


def _workers() -> tuple[WorkerSpec, ...]:
    return (
        WorkerSpec(
            slug="market_sizing",
            prompt_file="stage1/market_sizing.md",
            required_skills=("market-sizing",),
        ),
        WorkerSpec(slug="customer", prompt_file="stage1/customer.md"),
        WorkerSpec(slug="regulatory", prompt_file="stage1/regulatory.md"),
    )


def _state(run_id: uuid.UUID) -> RunState:
    return {
        "run_id": str(run_id),
        "goal": "x",
        "framing": {
            "objective": "obj",
            "target_market": "tm",
            "constraints": [],
            "questionnaire_answers": {},
        },
    }


def _worker_agent_ids(fake: RecordingFakeChatModel) -> list[str]:
    return [_agent_id_from_messages(messages) for _, messages in fake.structured_calls]


def _agent_id_from_messages(messages: Sequence[BaseMessage]) -> str:
    for message in messages:
        if isinstance(message, HumanMessage):
            content = str(message.content)
            for line in content.splitlines():
                if line.startswith("stage: "):
                    return line.removeprefix("stage: ")
    raise AssertionError("missing stage line")


@pytest.mark.asyncio
async def test_workers_fan_out_and_merge_output_state_and_persistence(run_id: uuid.UUID) -> None:
    fake = RecordingFakeChatModel(
        structured_responses={
            "stage1_foundation.market_sizing": {
                "artifacts": [{"path": "findings.md", "content": "Market sizing [^m1]."}],
                "evidence": [{"src_id": "m1", "title": "Market source"}],
                "summary": "Market complete",
            },
            "stage1_foundation.customer": {
                "artifacts": [{"path": "findings.md", "content": "Customer finding [^c1]."}],
                "evidence": [{"src_id": "c1", "title": "Customer source"}],
                "summary": "Customer complete",
            },
            "stage1_foundation.regulatory": {
                "artifacts": [{"path": "nested/findings.md", "content": "Reg finding [^r1]."}],
                "evidence": [{"src_id": "r1", "title": "Reg source"}],
                "summary": "Reg complete",
            },
        }
    )
    node = make_stage_node("stage1_foundation", model=fake, profile=_profile(workers=_workers()))

    out = await node(_state(run_id))

    assert out["artifacts"]["stage1_foundation/market_sizing/findings.md"] == "Market sizing [^m1]."
    assert out["artifacts"]["stage1_foundation/customer/findings.md"] == "Customer finding [^c1]."
    assert (
        out["artifacts"]["stage1_foundation/regulatory/nested/findings.md"] == "Reg finding [^r1]."
    )
    assert {e["src_id"] for e in out["evidence"]} == {"m1", "c1", "r1"}
    assert out["worker_outputs"]["stage1_foundation"] == {
        "market_sizing": {
            "summary": "Market complete",
            "artifact_paths": ["stage1_foundation/market_sizing/findings.md"],
            "evidence_ids": ["m1"],
        },
        "customer": {
            "summary": "Customer complete",
            "artifact_paths": ["stage1_foundation/customer/findings.md"],
            "evidence_ids": ["c1"],
        },
        "regulatory": {
            "summary": "Reg complete",
            "artifact_paths": ["stage1_foundation/regulatory/nested/findings.md"],
            "evidence_ids": ["r1"],
        },
    }

    async with AsyncSessionLocal() as session:
        artifact_paths = sorted(
            (
                await session.execute(select(Artifact.path).where(Artifact.run_id == run_id))
            ).scalars()
        )
        event_agents = sorted(
            (
                await session.execute(
                    select(Event.agent).where(
                        Event.run_id == run_id,
                        Event.type == "artifact_update",
                    )
                )
            ).scalars()
        )
    assert artifact_paths == [
        "stage1_foundation/customer/findings.md",
        "stage1_foundation/market_sizing/findings.md",
        "stage1_foundation/regulatory/nested/findings.md",
    ]
    assert event_agents == [
        "stage1_foundation.customer",
        "stage1_foundation.market_sizing",
        "stage1_foundation.regulatory",
    ]

    market_messages = next(
        messages
        for _, messages in fake.structured_calls
        if any(
            isinstance(message, HumanMessage)
            and "stage: stage1_foundation.market_sizing" in str(message.content)
            for message in messages
        )
    )
    market_system = next(
        message.content for message in market_messages if isinstance(message, SystemMessage)
    )
    assert "Applicable Consulting Skills" in str(market_system)
    assert "Evidence Discipline" in str(market_system)
    assert "Market Sizing" in str(market_system)


@pytest.mark.asyncio
async def test_worker_fanout_respects_worker_concurrency_cap(
    monkeypatch: pytest.MonkeyPatch,
    run_id: uuid.UUID,
) -> None:
    monkeypatch.setenv("WORKER_CONCURRENCY", "1")
    get_settings.cache_clear()
    fake = GateFakeChatModel()
    node = make_stage_node("stage1_foundation", model=fake, profile=_profile(workers=_workers()))

    try:
        await node(_state(run_id))
    finally:
        get_settings.cache_clear()

    assert fake.max_active == 1
    assert fake.started == [
        "stage1_foundation.market_sizing",
        "stage1_foundation.customer",
        "stage1_foundation.regulatory",
    ]
    assert fake.finished == fake.started


@pytest.mark.asyncio
async def test_worker_reiterate_with_worker_slug_runs_only_target_worker(
    run_id: uuid.UUID,
) -> None:
    fake = RecordingFakeChatModel(
        structured_responses={
            "stage1_foundation.customer": {
                "artifacts": [{"path": "findings.md", "content": "New customer [^c2]."}],
                "evidence": [{"src_id": "c2", "title": "Customer source 2"}],
                "summary": "Customer retry complete",
            }
        }
    )
    node = make_stage_node("stage1_foundation", model=fake, profile=_profile(workers=_workers()))
    state = _state(run_id)
    state["target_agents"] = ["customer"]
    state["artifacts"] = {
        "stage1_foundation/market_sizing/findings.md": "Accepted market [^m1].",
        "stage1_foundation/regulatory/findings.md": "Accepted regulatory [^r1].",
    }
    state["worker_outputs"] = {
        "stage1_foundation": {
            "market_sizing": {
                "summary": "Accepted market",
                "artifact_paths": ["stage1_foundation/market_sizing/findings.md"],
                "evidence_ids": ["m1"],
            },
            "regulatory": {
                "summary": "Accepted regulatory",
                "artifact_paths": ["stage1_foundation/regulatory/findings.md"],
                "evidence_ids": ["r1"],
            },
        }
    }

    out = await node(state)

    assert _worker_agent_ids(fake) == ["stage1_foundation.customer"]
    assert (
        out["artifacts"]["stage1_foundation/market_sizing/findings.md"] == "Accepted market [^m1]."
    )
    assert (
        out["artifacts"]["stage1_foundation/regulatory/findings.md"] == "Accepted regulatory [^r1]."
    )
    assert out["artifacts"]["stage1_foundation/customer/findings.md"] == "New customer [^c2]."
    assert out["worker_outputs"]["stage1_foundation"]["market_sizing"]["summary"] == (
        "Accepted market"
    )
    assert out["worker_outputs"]["stage1_foundation"]["regulatory"]["summary"] == (
        "Accepted regulatory"
    )
    assert out["worker_outputs"]["stage1_foundation"]["customer"] == {
        "summary": "Customer retry complete",
        "artifact_paths": ["stage1_foundation/customer/findings.md"],
        "evidence_ids": ["c2"],
    }


@pytest.mark.asyncio
async def test_worker_reiterate_accepts_dotted_worker_id(run_id: uuid.UUID) -> None:
    fake = RecordingFakeChatModel(
        structured_responses={
            "stage1_foundation.regulatory": {
                "artifacts": [{"path": "findings.md", "content": "Reg retry [^r2]."}],
                "evidence": [{"src_id": "r2", "title": "Reg source 2"}],
                "summary": "Reg retry complete",
            }
        }
    )
    node = make_stage_node("stage1_foundation", model=fake, profile=_profile(workers=_workers()))
    state = _state(run_id)
    state["target_agents"] = ["stage1_foundation.regulatory"]

    out = await node(state)

    assert _worker_agent_ids(fake) == ["stage1_foundation.regulatory"]
    assert out["artifacts"] == {"stage1_foundation/regulatory/findings.md": "Reg retry [^r2]."}


@pytest.mark.asyncio
async def test_worker_fanout_removes_write_artifact_tool(run_id: uuid.UUID) -> None:
    write_artifact = RecordingTool("write_artifact")
    lookup = RecordingTool("lookup_market")
    fake = FakeChatModel(
        responses=[
            AIMessage(
                content="Try direct artifact write",
                tool_calls=[
                    {
                        "name": "write_artifact",
                        "args": {
                            "path": "findings.md",
                            "kind": "markdown",
                            "content": "tool content",
                        },
                        "id": "call_write",
                    }
                ],
            ),
            AIMessage(content="Ready to finalize"),
        ],
        structured_responses=[
            {
                "artifacts": [{"path": "findings.md", "content": "Structured [^c3]."}],
                "evidence": [{"src_id": "c3", "title": "Customer source 3"}],
                "summary": "Customer complete",
            }
        ],
    )
    node = make_stage_node(
        "stage1_foundation",
        model=fake,
        tools=[write_artifact, lookup],
        profile=_profile(workers=_workers()),
    )
    state = _state(run_id)
    state["target_agents"] = ["customer"]

    out = await node(state)

    assert write_artifact.calls == []
    assert fake.bound_tools == [lookup]
    assert out["artifacts"] == {"stage1_foundation/customer/findings.md": "Structured [^c3]."}
    _, structured_messages = fake.structured_calls[0]
    assert any(
        isinstance(message, ToolMessage)
        and message.tool_call_id == "call_write"
        and "Tool not found: write_artifact" in str(message.content)
        for message in structured_messages
    )
    async with AsyncSessionLocal() as session:
        artifact_rows = (
            (await session.execute(select(Artifact).where(Artifact.run_id == run_id)))
            .scalars()
            .all()
        )
        event_rows = (
            (await session.execute(select(Event).where(Event.run_id == run_id))).scalars().all()
        )
    assert [(row.path, row.content) for row in artifact_rows] == [
        ("stage1_foundation/customer/findings.md", "Structured [^c3].")
    ]
    assert {event.agent for event in event_rows if event.type == "artifact_update"} == {
        "stage1_foundation.customer"
    }


@pytest.mark.asyncio
async def test_stage_without_workers_uses_single_stage_react_path(run_id: uuid.UUID) -> None:
    fake = FakeChatModel(
        structured_responses=[
            {
                "artifacts": [{"path": "stage1_foundation/findings.md", "content": "Stage [^s1]."}],
                "evidence": [{"src_id": "s1", "title": "Stage source"}],
                "summary": "Stage complete",
            }
        ]
    )
    node = make_stage_node("stage1_foundation", model=fake, profile=_profile(workers=()))

    out = await node(_state(run_id))

    assert out["artifacts"] == {"stage1_foundation/findings.md": "Stage [^s1]."}
    assert "worker_outputs" not in out
    _, messages = fake.structured_calls[0]
    assert any(
        isinstance(message, HumanMessage) and "stage: stage1_foundation\n" in str(message.content)
        for message in messages
    )

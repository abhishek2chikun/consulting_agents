"""Integration tests for stage-node ReAct tool loops."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from langchain_core.messages import AIMessage, ToolMessage
from sqlalchemy import select

from app.agents.market_entry.nodes.stage import make_stage_node
from app.agents.market_entry.state import RunState
from app.core.config import get_settings
from app.core.db import AsyncSessionLocal
from app.models import SINGLETON_USER_ID, Artifact, Event, Run, RunStatus
from app.testing.fake_chat_model import FakeChatModel


class FakeTool:
    name = "lookup_market"

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def invoke(self, args: dict[str, Any]) -> str:
        self.calls.append(args)
        return "tool result: market CAGR is 12%"


class AsyncFakeTool:
    name = "lookup_market_async"

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def ainvoke(self, args: dict[str, Any]) -> str:
        self.calls.append(args)
        return "async tool result: market CAGR is 14%"


class UnsupportedBindFakeChatModel(FakeChatModel):
    def bind_tools(self, tools: Any, **kwargs: Any) -> Any:
        raise NotImplementedError


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


def _payload(path: str = "stage1_foundation/findings.md") -> dict[str, Any]:
    return {
        "artifacts": [{"path": path, "content": "Finding from tool [^s1]."}],
        "evidence": [{"src_id": "s1", "title": "Source 1", "snippet": "Snippet"}],
        "summary": "stage complete",
    }


def _malformed_tool_call_message(tool_calls: list[dict[str, Any]]) -> AIMessage:
    message = AIMessage(content="Malformed tool call")
    object.__setattr__(message, "tool_calls", tool_calls)
    return message


@pytest.mark.asyncio
async def test_stage_node_executes_tool_call_before_structured_output(
    run_id: uuid.UUID,
) -> None:
    tool = FakeTool()
    fake = FakeChatModel(
        responses=[
            AIMessage(
                content="Need market data",
                tool_calls=[
                    {
                        "name": "lookup_market",
                        "args": {"query": "EU EV charging CAGR"},
                        "id": "call_1",
                    }
                ],
            ),
            AIMessage(content="Ready to finalize"),
        ],
        structured_responses=[_payload()],
    )
    node = make_stage_node("stage1_foundation", model=fake, tools=[tool])

    out = await node(_state(run_id))

    assert tool.calls == [{"query": "EU EV charging CAGR"}]
    assert fake.bound_tools == [tool]
    _, structured_messages = fake.structured_calls[0]
    assert any(
        isinstance(message, ToolMessage) and message.content == "tool result: market CAGR is 12%"
        for message in structured_messages
    )
    assert out["artifacts"]["stage1_foundation/findings.md"].startswith("Finding")

    async with AsyncSessionLocal() as session:
        artifact_rows = (
            (await session.execute(select(Artifact).where(Artifact.run_id == run_id)))
            .scalars()
            .all()
        )
    assert len(artifact_rows) == 1
    assert artifact_rows[0].path == "stage1_foundation/findings.md"


@pytest.mark.asyncio
async def test_stage_node_no_tools_fallback_does_not_emit_no_tool_warning(
    run_id: uuid.UUID,
) -> None:
    fake = FakeChatModel(structured_responses=[_payload()])
    node = make_stage_node("stage1_foundation", model=fake)

    await node(_state(run_id))

    assert len(fake.calls) == 0
    async with AsyncSessionLocal() as session:
        warning_rows = (
            (
                await session.execute(
                    select(Event).where(
                        Event.run_id == run_id,
                        Event.type == "agent_message",
                        Event.payload["text"].astext.contains(
                            "produced StageOutput without tool use"
                        ),
                    )
                )
            )
            .scalars()
            .all()
        )
    assert warning_rows == []


@pytest.mark.asyncio
async def test_stage_node_warns_when_tools_provided_but_model_uses_none(
    run_id: uuid.UUID,
) -> None:
    fake = FakeChatModel(
        responses=[AIMessage(content="No tool needed")],
        structured_responses=[_payload()],
    )
    node = make_stage_node("stage1_foundation", model=fake, tools=[FakeTool()])

    await node(_state(run_id))

    async with AsyncSessionLocal() as session:
        warning_rows = (
            (
                await session.execute(
                    select(Event).where(
                        Event.run_id == run_id,
                        Event.type == "agent_message",
                        Event.payload["text"].astext.contains(
                            "stage1_foundation: produced StageOutput without tool use"
                        ),
                    )
                )
            )
            .scalars()
            .all()
        )
    assert len(warning_rows) == 1
    assert warning_rows[0].agent == "stage1_foundation"


@pytest.mark.asyncio
async def test_stage_node_max_iteration_cap_still_finalizes(
    monkeypatch: pytest.MonkeyPatch,
    run_id: uuid.UUID,
) -> None:
    monkeypatch.setenv("REACT_MAX_ITERATIONS", "1")
    get_settings.cache_clear()
    tool = FakeTool()
    fake = FakeChatModel(
        responses=[
            AIMessage(
                content="Need first lookup",
                tool_calls=[
                    {
                        "name": "lookup_market",
                        "args": {"query": "first"},
                        "id": "call_1",
                    }
                ],
            ),
            AIMessage(
                content="Would call again",
                tool_calls=[
                    {
                        "name": "lookup_market",
                        "args": {"query": "second"},
                        "id": "call_2",
                    }
                ],
            ),
        ],
        structured_responses=[_payload()],
    )
    node = make_stage_node("stage1_foundation", model=fake, tools=[tool])

    await node(_state(run_id))

    assert tool.calls == [{"query": "first"}]
    assert len(fake.calls) == 1
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_stage_node_bind_tools_not_implemented_falls_back_and_finalizes(
    run_id: uuid.UUID,
) -> None:
    fake = UnsupportedBindFakeChatModel(
        responses=[AIMessage(content="No tool needed")],
        structured_responses=[_payload()],
    )
    node = make_stage_node("stage1_foundation", model=fake, tools=[FakeTool()])

    out = await node(_state(run_id))

    assert out["artifacts"]["stage1_foundation/findings.md"].startswith("Finding")
    async with AsyncSessionLocal() as session:
        warning_rows = (
            (
                await session.execute(
                    select(Event).where(
                        Event.run_id == run_id,
                        Event.type == "agent_message",
                        Event.payload["text"].astext.contains(
                            "stage1_foundation: produced StageOutput without tool use"
                        ),
                    )
                )
            )
            .scalars()
            .all()
        )
    assert len(warning_rows) == 1


@pytest.mark.asyncio
async def test_stage_node_unknown_tool_name_appends_error_and_finalizes(
    run_id: uuid.UUID,
) -> None:
    fake = FakeChatModel(
        responses=[
            AIMessage(
                content="Try unavailable tool",
                tool_calls=[
                    {
                        "name": "missing_tool",
                        "args": {"query": "EU EV charging"},
                        "id": "call_missing",
                    }
                ],
            ),
            AIMessage(content="Ready to finalize"),
        ],
        structured_responses=[_payload()],
    )
    node = make_stage_node("stage1_foundation", model=fake, tools=[FakeTool()])

    await node(_state(run_id))

    _, structured_messages = fake.structured_calls[0]
    assert any(
        isinstance(message, ToolMessage)
        and message.tool_call_id == "call_missing"
        and "Tool not found: missing_tool" in str(message.content)
        for message in structured_messages
    )


@pytest.mark.asyncio
async def test_stage_node_malformed_tool_call_missing_name_appends_error_and_finalizes(
    run_id: uuid.UUID,
) -> None:
    fake = FakeChatModel(
        responses=[
            _malformed_tool_call_message([{"args": {"query": "EU EV charging"}, "id": "bad_1"}]),
            AIMessage(content="Ready to finalize"),
        ],
        structured_responses=[_payload()],
    )
    node = make_stage_node("stage1_foundation", model=fake, tools=[FakeTool()])

    await node(_state(run_id))

    _, structured_messages = fake.structured_calls[0]
    assert any(
        isinstance(message, ToolMessage)
        and message.tool_call_id == "bad_1"
        and "Malformed tool call: missing tool name" in str(message.content)
        for message in structured_messages
    )


@pytest.mark.asyncio
async def test_stage_node_invokes_async_tool_with_default_args_when_args_missing(
    run_id: uuid.UUID,
) -> None:
    tool = AsyncFakeTool()
    fake = FakeChatModel(
        responses=[
            _malformed_tool_call_message(
                [
                    {
                        "name": "lookup_market_async",
                        "id": "async_call",
                    }
                ]
            ),
            AIMessage(content="Ready to finalize"),
        ],
        structured_responses=[_payload()],
    )
    node = make_stage_node("stage1_foundation", model=fake, tools=[tool])

    await node(_state(run_id))

    assert tool.calls == [{}]
    _, structured_messages = fake.structured_calls[0]
    assert any(
        isinstance(message, ToolMessage)
        and message.tool_call_id == "async_call"
        and message.content == "async tool result: market CAGR is 14%"
        for message in structured_messages
    )

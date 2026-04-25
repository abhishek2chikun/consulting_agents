"""Integration tests for run lifecycle APIs (M5.5)."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy import delete, select

from app.core.db import AsyncSessionLocal
from app.main import create_app
from app.models import Artifact, Message, Run, RunStatus


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _cleanup_run(run_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(delete(Run).where(Run.id == run_id))
        await session.commit()


async def _read_one_sse_event(response: httpx.Response, timeout: float = 3.0) -> dict[str, object]:
    event_id: int | None = None
    data: str | None = None
    line_iter = response.aiter_lines()
    deadline = asyncio.get_event_loop().time() + timeout

    while True:
        remaining = deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            break
        try:
            line = await asyncio.wait_for(anext(line_iter), timeout=remaining)
        except (StopAsyncIteration, TimeoutError):
            break

        if line.startswith("id: "):
            event_id = int(line.removeprefix("id: ").strip())
        elif line.startswith("data: "):
            data = line.removeprefix("data: ")
        elif line == "" and event_id is not None and data is not None:
            break

    assert event_id is not None
    assert data is not None
    payload = json.loads(data)
    assert isinstance(payload, dict)
    return payload


async def _wait_for_artifact_path(
    client: httpx.AsyncClient,
    run_id: uuid.UUID,
    path: str,
    timeout: float = 3.0,
) -> None:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        meta = await client.get(f"/runs/{run_id}")
        if meta.status_code == 200 and path in meta.json()["artifact_paths"]:
            return
        await asyncio.sleep(0.1)
    raise AssertionError(f"Artifact {path!r} not ready within {timeout}s")


async def _wait_for_message_count(
    run_id: uuid.UUID,
    expected_at_least: int,
    timeout: float = 3.0,
) -> None:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        async with AsyncSessionLocal() as session:
            messages = (
                await session.execute(select(Message).where(Message.run_id == run_id))
            ).scalars()
            if len(list(messages)) >= expected_at_least:
                return
        await asyncio.sleep(0.1)
    raise AssertionError(
        f"Message count for run {run_id} did not reach {expected_at_least} within {timeout}s"
    )


@pytest.mark.asyncio
async def test_post_runs_creates_questioning_run_and_emits_questionnaire_event(
    client: httpx.AsyncClient,
) -> None:
    resp = await client.post(
        "/runs",
        json={
            "task_type": "market_entry",
            "goal": "Evaluate expansion into a new region",
            "document_ids": [],
        },
    )
    assert resp.status_code == 201, resp.text
    run_id = uuid.UUID(resp.json()["run_id"])

    try:
        async with AsyncSessionLocal() as session:
            run = await session.get(Run, run_id)
            assert run is not None
            assert run.status == RunStatus.questioning

        async with client.stream("GET", f"/runs/{run_id}/stream?max_events=1") as stream_resp:
            assert stream_resp.status_code == 200
            event = await _read_one_sse_event(stream_resp)

        assert event["type"] == "artifact_update"
        event_payload = event["payload"]
        assert isinstance(event_payload, dict)
        assert event_payload["path"] == "framing/questionnaire.json"

        meta = await client.get(f"/runs/{run_id}")
        assert meta.status_code == 200
        assert "framing/questionnaire.json" in meta.json()["artifact_paths"]
    finally:
        await _cleanup_run(run_id)


@pytest.mark.asyncio
async def test_answers_and_artifact_fetch_roundtrip(client: httpx.AsyncClient) -> None:
    create = await client.post(
        "/runs",
        json={
            "task_type": "market_entry",
            "goal": "Plan market entry",
            "document_ids": [],
        },
    )
    assert create.status_code == 201, create.text
    run_id = uuid.UUID(create.json()["run_id"])

    try:
        await _wait_for_artifact_path(client, run_id, "framing/questionnaire.json")

        submit = await client.post(
            f"/runs/{run_id}/answers",
            json={"answers": {"time_horizon": "12 months", "budget": "medium"}},
        )
        assert submit.status_code == 204, submit.text
        await _wait_for_message_count(run_id, 1)

        artifact = await client.get(f"/runs/{run_id}/artifacts/framing/questionnaire.json")
        assert artifact.status_code == 200
        parsed = artifact.json()
        assert isinstance(parsed, dict)
        assert parsed["path"] == "framing/questionnaire.json"
        assert parsed["kind"] == "json"
        content = json.loads(parsed["content"])
        assert "items" in content

        async with AsyncSessionLocal() as session:
            run = await session.get(Run, run_id)
            assert run is not None
            assert run.status == RunStatus.running

            messages = (
                await session.execute(select(Message).where(Message.run_id == run_id))
            ).scalars()
            assert len(list(messages)) == 1

            artifacts = (
                await session.execute(select(Artifact).where(Artifact.run_id == run_id))
            ).scalars()
            assert len(list(artifacts)) >= 1
    finally:
        await _cleanup_run(run_id)

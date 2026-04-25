"""Integration tests for run lifecycle APIs (M5.5 + M6.11).

The worker now drives the full LangGraph pipeline (framing → stages →
synthesis → audit) instead of writing a hard-coded questionnaire, so we
override `get_run_model_factory_builder` with a `FakeChatModel`-backed factory
to keep the test self-contained (no API keys, no network).
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable

import httpx
import pytest
from sqlalchemy import delete, select

from app.api.runs import get_run_model_factory_builder
from app.core.db import AsyncSessionLocal
from app.main import create_app
from app.models import Artifact, Message, Run, RunStatus
from app.testing.fake_chat_model import FakeChatModel
from app.workers.run_worker import ModelFactory


def _stage_payload(stage_slug: str, src_id: str) -> dict:
    return {
        "artifacts": [
            {
                "path": f"{stage_slug}/findings.md",
                "content": f"{stage_slug} finding [^{src_id}].",
                "kind": "markdown",
            }
        ],
        "evidence": [
            {
                "src_id": src_id,
                "title": f"{stage_slug} source",
                "url": f"https://example.com/{src_id}",
                "snippet": "snippet",
                "kind": "web",
                "provider": "tavily",
            }
        ],
        "summary": f"{stage_slug} summary",
    }


def _gate(stage: str, verdict: str) -> dict:
    return {
        "verdict": verdict,
        "stage": stage,
        "attempt": 1,
        "gaps": [],
        "target_agents": [],
        "rationale": "ok",
    }


def _fresh_factory() -> ModelFactory:
    """Return a fresh per-role factory; each call to the dep gives new queues.

    The lifecycle test creates two runs (one per test), and FastAPI
    resolves the dependency once per request — so we need a factory
    that hands out new `FakeChatModel`s populated with enough scripted
    responses for one full run.
    """

    framing_response = {
        "brief": {
            "objective": "Plan",
            "target_market": "EU",
            "constraints": [],
            "questionnaire_answers": {},
        },
        "questionnaire": {
            "items": [
                {
                    "id": "time_horizon",
                    "label": "Time horizon",
                    "type": "text",
                    "required": True,
                }
            ]
        },
    }

    framing_model = FakeChatModel(structured_responses=[framing_response])
    research_model = FakeChatModel(
        structured_responses=[
            _stage_payload("stage1_foundation", "s1"),
            _stage_payload("stage2_competitive", "s2"),
            _stage_payload("stage3_risk", "s3"),
            _stage_payload("stage4_demand", "s4"),
            _stage_payload("stage5_strategy", "s5"),
        ]
    )
    reviewer_model = FakeChatModel(
        structured_responses=[
            _gate("stage1_foundation", "advance"),
            _gate("stage2_competitive", "advance"),
            _gate("stage3_risk", "advance"),
            _gate("stage4_demand", "advance"),
            _gate("stage5_strategy", "advance"),
        ]
    )
    synthesis_model = FakeChatModel(
        responses=[
            "# Final Report\n\n## Executive Summary\n"
            "- s1 [^s1] s2 [^s2] s3 [^s3] s4 [^s4] s5 [^s5].\n"
        ]
    )
    audit_model = FakeChatModel(
        responses=["## Weak Claims\n- none\n## Contradictions\n- none\n## Residual Gaps\n- none\n"]
    )

    cache: dict[str, FakeChatModel] = {
        "framing": framing_model,
        "research": research_model,
        "reviewer": reviewer_model,
        "synthesis": synthesis_model,
        "audit": audit_model,
    }

    def factory(role: str) -> object:
        return cache[role]

    return factory


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    app = create_app()

    async def _override() -> Callable[[uuid.UUID], Awaitable[ModelFactory]]:
        async def _build(_run_id: uuid.UUID) -> ModelFactory:
            return _fresh_factory()

        return _build

    app.dependency_overrides[get_run_model_factory_builder] = _override

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()


async def _cleanup_run(run_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(delete(Run).where(Run.id == run_id))
        await session.commit()


async def _read_one_sse_event(response: httpx.Response, timeout: float = 5.0) -> dict[str, object]:
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
    timeout: float = 5.0,
) -> None:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        meta = await client.get(f"/runs/{run_id}")
        if meta.status_code == 200 and path in meta.json()["artifact_paths"]:
            return
        await asyncio.sleep(0.1)
    raise AssertionError(f"Artifact {path!r} not ready within {timeout}s")


async def _wait_for_run_status(
    run_id: uuid.UUID,
    expected: RunStatus,
    timeout: float = 10.0,
) -> None:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        async with AsyncSessionLocal() as session:
            run = await session.get(Run, run_id)
            if run is not None and run.status == expected:
                return
        await asyncio.sleep(0.1)
    raise AssertionError(f"Run {run_id} did not reach status {expected!r} within {timeout}s")


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
async def test_answers_drive_full_pipeline_and_persist_artifacts(
    client: httpx.AsyncClient,
) -> None:
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

        # Worker now drives the full pipeline; wait for completion.
        await _wait_for_run_status(run_id, RunStatus.completed)

        artifact = await client.get(f"/runs/{run_id}/artifacts/framing/questionnaire.json")
        assert artifact.status_code == 200
        parsed = artifact.json()
        assert isinstance(parsed, dict)
        assert parsed["path"] == "framing/questionnaire.json"
        assert parsed["kind"] == "json"
        content = json.loads(parsed["content"])
        assert "items" in content

        async with AsyncSessionLocal() as session:
            messages = (
                (await session.execute(select(Message).where(Message.run_id == run_id)))
                .scalars()
                .all()
            )
            assert len(messages) == 1

            artifact_paths = {
                a.path
                for a in (await session.execute(select(Artifact).where(Artifact.run_id == run_id)))
                .scalars()
                .all()
            }
        assert "stage1_foundation/findings.md" in artifact_paths
        assert "stage2_competitive/findings.md" in artifact_paths
        assert "stage3_risk/findings.md" in artifact_paths
        assert "stage4_demand/findings.md" in artifact_paths
        assert "stage5_strategy/findings.md" in artifact_paths
        assert "final_report.md" in artifact_paths
        assert "audit.md" in artifact_paths
    finally:
        await _cleanup_run(run_id)

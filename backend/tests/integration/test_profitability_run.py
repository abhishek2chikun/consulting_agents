"""Integration smoke test for profitability runs."""

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
                "content": f"{stage_slug} profitability finding [^{src_id}].",
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


def _gate(stage: str) -> dict:
    return {
        "verdict": "advance",
        "stage": stage,
        "attempt": 1,
        "gaps": [],
        "target_agents": [],
        "rationale": "ok",
    }


def _fresh_factory() -> ModelFactory:
    framing_response = {
        "brief": {
            "objective": "Improve profitability",
            "target_market": "SaaS segments",
            "constraints": [],
            "questionnaire_answers": {},
        },
        "questionnaire": {
            "items": [
                {
                    "id": "profit_pool",
                    "label": "Which product or segment should we diagnose?",
                    "type": "text",
                    "required": True,
                }
            ]
        },
    }
    stage_slugs = [
        "stage1_revenue",
        "stage2_cost",
        "stage3_margin",
        "stage4_competitor",
        "stage5_levers",
    ]

    models: dict[str, FakeChatModel] = {
        "framing": FakeChatModel(structured_responses=[framing_response]),
        "research": FakeChatModel(
            structured_responses=[
                _stage_payload(stage_slug, f"p{index}")
                for index, stage_slug in enumerate(stage_slugs, start=1)
            ]
        ),
        "reviewer": FakeChatModel(
            structured_responses=[_gate(stage_slug) for stage_slug in stage_slugs]
        ),
        "synthesis": FakeChatModel(
            responses=[
                "# Profitability Final Report\n\n## Executive Summary\n"
                "- Revenue, cost, margin, competitor, and lever findings [^p1].\n"
            ]
        ),
        "audit": FakeChatModel(
            responses=[
                "## Weak Claims\n- none\n## Contradictions\n- none\n## Residual Gaps\n- none\n"
            ]
        ),
    }

    def factory(role: str) -> object:
        return models[role]

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
async def test_profitability_answers_drive_full_pipeline_and_persist_artifacts(
    client: httpx.AsyncClient,
) -> None:
    create = await client.post(
        "/runs",
        json={
            "task_type": "profitability",
            "goal": "Diagnose product profitability",
            "document_ids": [],
        },
    )
    assert create.status_code == 201, create.text
    run_id = uuid.UUID(create.json()["run_id"])

    try:
        await _wait_for_artifact_path(client, run_id, "framing/questionnaire.json")

        submit = await client.post(
            f"/runs/{run_id}/answers",
            json={"answers": {"profit_pool": "Enterprise SaaS"}},
        )
        assert submit.status_code == 204, submit.text

        await _wait_for_run_status(run_id, RunStatus.completed)

        async with AsyncSessionLocal() as session:
            messages = (
                (await session.execute(select(Message).where(Message.run_id == run_id)))
                .scalars()
                .all()
            )
            artifact_paths = {
                a.path
                for a in (await session.execute(select(Artifact).where(Artifact.run_id == run_id)))
                .scalars()
                .all()
            }

        assert len(messages) == 1
        assert "stage1_revenue/findings.md" in artifact_paths
        assert "stage2_cost/findings.md" in artifact_paths
        assert "stage3_margin/findings.md" in artifact_paths
        assert "stage4_competitor/findings.md" in artifact_paths
        assert "stage5_levers/findings.md" in artifact_paths
        assert "final_report.md" in artifact_paths
        assert "audit.md" in artifact_paths

        artifact = await client.get(f"/runs/{run_id}/artifacts/final_report.md")
        assert artifact.status_code == 200
        parsed = artifact.json()
        assert parsed["path"] == "final_report.md"
        assert "Profitability Final Report" in parsed["content"]
        json.dumps(parsed)
    finally:
        await _cleanup_run(run_id)

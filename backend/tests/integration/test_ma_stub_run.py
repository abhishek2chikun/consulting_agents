"""Smoke test for the M&A V2 stub graph (M8.1).

Verifies that selecting `task_type="ma"` runs the placeholder graph
end-to-end:

* Run is created.
* Task registry dispatches to `run_ma_stub`.
* `final_report.md` artifact lands.
* `Run.status` ends up `completed` with no questionnaire artifact.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.main import create_app
from app.models import Artifact, Run, RunStatus


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _wait_for_completion(run_id: str, timeout: float = 5.0) -> Run:
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        async with AsyncSessionLocal() as session:
            run = await session.get(Run, run_id)
            assert run is not None
            if run.status in (
                RunStatus.completed,
                RunStatus.failed,
                RunStatus.cancelled,
            ):
                return run
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError(
                f"M&A stub run did not finish in {timeout}s; "
                f"last status={run.status if run else 'missing'}"
            )
        await asyncio.sleep(0.05)


@pytest.mark.asyncio
async def test_ma_stub_run_completes_with_placeholder_report(
    client: httpx.AsyncClient,
) -> None:
    res = await client.post(
        "/runs",
        json={
            "task_type": "ma",
            "goal": "Acquire a competitor in adjacent vertical",
            "document_ids": [],
        },
    )
    assert res.status_code == 201, res.text
    run_id = res.json()["run_id"]

    run = await _wait_for_completion(run_id)
    assert run.status is RunStatus.completed

    async with AsyncSessionLocal() as session:
        artifacts = (
            (await session.execute(select(Artifact).where(Artifact.run_id == run.id)))
            .scalars()
            .all()
        )

    paths = {a.path for a in artifacts}
    assert paths == {"final_report.md"}, paths

    report = next(a for a in artifacts if a.path == "final_report.md")
    assert report.kind == "markdown"
    # The placeholder template must include the user's goal verbatim
    # and explicitly call out the V2-stub status.
    assert "Acquire a competitor in adjacent vertical" in report.content
    assert "V2" in report.content

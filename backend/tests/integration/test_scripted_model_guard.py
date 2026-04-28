"""Integration coverage for the production-only run model factory wiring."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable

import httpx
import pytest

from app.agents.market_entry.profile import MARKET_ENTRY_PROFILE
from app.api.runs import get_run_model_factory_builder
from app.main import create_app
from app.testing.fake_chat_model import FakeChatModel
from app.workers import run_worker
from app.workers.run_worker import ModelFactory


class _NonProductionModel:
    def with_config(self, **_: object) -> _NonProductionModel:
        return self


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_post_runs_rejects_model_factory_field(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/runs",
        json={
            "task_type": "market_entry",
            "goal": "Evaluate expansion into a new region",
            "document_ids": [],
            "model_factory": "scripted-test-double",
        },
    )

    assert response.status_code in {400, 422}


@pytest.mark.asyncio
async def test_post_runs_rejects_testing_field(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/runs",
        json={
            "task_type": "market_entry",
            "goal": "Evaluate expansion into a new region",
            "document_ids": [],
            "testing": {"scripted_model": True},
        },
    )

    assert response.status_code in {400, 422}


@pytest.mark.asyncio
async def test_submit_answers_rejects_model_factory_field(client: httpx.AsyncClient) -> None:
    response = await client.post(
        f"/runs/{uuid.uuid4()}/answers",
        json={
            "answers": {"time_horizon": "12 months"},
            "model_factory": "scripted-test-double",
        },
    )

    assert response.status_code in {400, 422}


@pytest.mark.asyncio
async def test_default_model_factory_rejects_unmarked_model_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _sentinel_get_chat_model(role: str, *, session: object) -> object:
        assert session is not None
        return _NonProductionModel()

    monkeypatch.setattr(run_worker, "get_chat_model", _sentinel_get_chat_model)

    with pytest.raises(RuntimeError, match="production"):
        await run_worker.default_model_factory(uuid.uuid4())


@pytest.mark.asyncio
async def test_dependency_override_still_allows_scripted_factory_in_tests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app()

    async def _override() -> Callable[[uuid.UUID], Awaitable[ModelFactory]]:
        async def _build(_run_id: uuid.UUID) -> ModelFactory:
            scripted = FakeChatModel(responses=["ok"])

            def _factory(_role: str) -> object:
                return scripted

            return _factory

        return _build

    app.dependency_overrides[get_run_model_factory_builder] = _override

    captured: dict[str, object] = {}
    started = asyncio.Event()

    async def _record_start_framing(
        run_id: uuid.UUID,
        *,
        profile: object,
        model_factory: ModelFactory | None = None,
    ) -> None:
        captured["run_id"] = run_id
        captured["profile"] = profile
        captured["model"] = None if model_factory is None else model_factory("framing")
        started.set()

    monkeypatch.setattr("app.api.runs.start_framing", _record_start_framing)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/runs",
            json={
                "task_type": "market_entry",
                "goal": "Check override path",
                "document_ids": [],
            },
        )

    assert response.status_code == 201, response.text
    await asyncio.wait_for(started.wait(), timeout=2.0)
    assert captured["profile"] == MARKET_ENTRY_PROFILE
    assert isinstance(captured["model"], FakeChatModel)

"""Integration tests for BudgetTracker (M7.1).

The tracker is an async LangChain callback handler that:
  * accumulates `AIMessage.usage_metadata` per (provider, model)
  * computes USD cost via `app.agents.pricing.cost_for`
  * persists rolling totals onto `Run.model_snapshot["usage"]`
  * publishes a `usage_update` SSE event after each LLM call
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult
from sqlalchemy import select

from app.agents.budget import BudgetTracker
from app.core.db import AsyncSessionLocal
from app.models import SINGLETON_USER_ID, Event, Run, RunStatus


@pytest_asyncio.fixture
async def fresh_run() -> AsyncIterator[uuid.UUID]:
    async with AsyncSessionLocal() as session:
        run = Run(
            user_id=SINGLETON_USER_ID,
            task_id="market_entry",
            goal="track usage",
            status=RunStatus.running,
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        yield run.id


def _llm_result(model_name: str, input_tokens: int, output_tokens: int) -> LLMResult:
    msg = AIMessage(
        content="hello",
        usage_metadata={
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        },
        response_metadata={"model_name": model_name},
    )
    return LLMResult(generations=[[ChatGeneration(message=msg)]])


@pytest.mark.asyncio
async def test_budget_tracker_persists_totals_and_publishes_event(
    fresh_run: uuid.UUID,
) -> None:
    tracker = BudgetTracker(run_id=fresh_run, provider="anthropic")

    # Simulate two LLM calls
    await tracker.on_llm_end(_llm_result("claude-sonnet-4-5", 1000, 500))
    await tracker.on_llm_end(_llm_result("claude-sonnet-4-5", 2000, 800))

    async with AsyncSessionLocal() as session:
        run = await session.get(Run, fresh_run)
        events = (
            await session.execute(
                select(Event).where(
                    Event.run_id == fresh_run,
                    Event.type == "usage_update",
                )
            )
        ).scalars().all()

    assert run is not None
    usage = run.model_snapshot.get("usage")
    assert usage is not None
    assert usage["input_tokens"] == 3000
    assert usage["output_tokens"] == 1300
    assert usage["total_tokens"] == 4300
    # Cost: (3000/1e6)*3.0 + (1300/1e6)*15.0 = 0.009 + 0.0195 = 0.0285
    assert usage["cost_usd"] == pytest.approx(0.0285, rel=1e-6)
    # Per-model breakdown preserved
    assert "claude-sonnet-4-5" in usage["by_model"]
    assert usage["by_model"]["claude-sonnet-4-5"]["input_tokens"] == 3000

    assert len(events) == 2
    last_payload = events[-1].payload
    assert last_payload["input_tokens"] == 3000
    assert last_payload["output_tokens"] == 1300


@pytest.mark.asyncio
async def test_budget_tracker_skips_calls_without_usage_metadata(
    fresh_run: uuid.UUID,
) -> None:
    tracker = BudgetTracker(run_id=fresh_run, provider="anthropic")

    msg = AIMessage(content="no usage")  # no usage_metadata, no model_name
    await tracker.on_llm_end(LLMResult(generations=[[ChatGeneration(message=msg)]]))

    async with AsyncSessionLocal() as session:
        run = await session.get(Run, fresh_run)
        events = (
            await session.execute(
                select(Event).where(
                    Event.run_id == fresh_run,
                    Event.type == "usage_update",
                )
            )
        ).scalars().all()

    assert run is not None
    # No usage block created when nothing was tracked
    assert "usage" not in run.model_snapshot
    assert events == []


@pytest.mark.asyncio
async def test_budget_tracker_unknown_model_zero_cost(
    fresh_run: uuid.UUID,
) -> None:
    tracker = BudgetTracker(run_id=fresh_run, provider="anthropic")

    await tracker.on_llm_end(_llm_result("brand-new-frontier-model", 1000, 500))

    async with AsyncSessionLocal() as session:
        run = await session.get(Run, fresh_run)

    assert run is not None
    usage = run.model_snapshot["usage"]
    assert usage["input_tokens"] == 1000
    assert usage["output_tokens"] == 500
    assert usage["cost_usd"] == 0.0  # unknown model → zero

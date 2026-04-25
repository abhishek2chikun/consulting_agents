"""Per-run usage/cost tracker (M7.1).

A LangChain `AsyncCallbackHandler` that taps `AIMessage.usage_metadata`
on every chat call, accumulates per-model totals, computes USD cost via
the static price table in :mod:`app.agents.pricing`, and persists
rolling totals onto ``Run.model_snapshot["usage"]``. After each
successful update it publishes a ``usage_update`` SSE event so the UI
can render a live counter.

Design notes
------------
* We attach **one** tracker per run, not one per role. The handler
  internally bins usage by ``response_metadata["model_name"]``, which
  uniquely identifies the model regardless of the role bucket.
* ``provider`` is supplied at construction. V1 uses a single provider
  per run (resolved at run start by ``default_model_factory``), so this
  matches reality. If a future role override mixes providers we would
  need to derive provider per-call from the model name; for now we
  document the limitation and move on.
* The handler is async to avoid having to schedule fire-and-forget
  tasks from a sync `on_llm_end`. `langchain_core` invokes the async
  variant when a chat model is driven via `ainvoke`, which is the only
  path used by the agent graph.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult
from sqlalchemy.orm.attributes import flag_modified

from app.agents.pricing import cost_for
from app.core.db import AsyncSessionLocal
from app.core.events import publish
from app.models import Run

logger = logging.getLogger(__name__)


class BudgetTracker(AsyncCallbackHandler):
    """Accumulate per-run token usage + cost across every chat call."""

    def __init__(self, *, run_id: uuid.UUID, provider: str) -> None:
        super().__init__()
        self._run_id = run_id
        self._provider = provider
        self._lock = asyncio.Lock()

    async def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        usage_metadata, model_name = _extract_usage(response)
        if usage_metadata is None or model_name is None:
            return

        input_tokens = int(usage_metadata.get("input_tokens", 0) or 0)
        output_tokens = int(usage_metadata.get("output_tokens", 0) or 0)
        if input_tokens == 0 and output_tokens == 0:
            return

        call_cost = cost_for(
            provider=self._provider,
            model=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        async with self._lock:
            try:
                snapshot = await self._update_run_snapshot(
                    model_name=model_name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    call_cost=call_cost,
                )
            except Exception:  # pragma: no cover - defensive
                logger.exception(
                    "BudgetTracker failed to update run %s", self._run_id
                )
                return

        # Publish outside the lock so SSE backpressure can't stall the
        # next callback.
        await publish(
            self._run_id,
            "usage_update",
            {
                "input_tokens": snapshot["input_tokens"],
                "output_tokens": snapshot["output_tokens"],
                "total_tokens": snapshot["total_tokens"],
                "cost_usd": snapshot["cost_usd"],
                "model_name": model_name,
                "delta": {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cost_usd": call_cost,
                },
            },
            agent="budget",
        )

    async def _update_run_snapshot(
        self,
        *,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        call_cost: float,
    ) -> dict[str, Any]:
        """Mutate Run.model_snapshot["usage"] in a single transaction."""
        async with AsyncSessionLocal() as session:
            run = await session.get(Run, self._run_id)
            if run is None:
                raise RuntimeError(f"run {self._run_id} disappeared")

            snapshot = dict(run.model_snapshot or {})
            usage = dict(snapshot.get("usage") or {})

            usage["input_tokens"] = int(usage.get("input_tokens", 0)) + input_tokens
            usage["output_tokens"] = int(usage.get("output_tokens", 0)) + output_tokens
            usage["total_tokens"] = usage["input_tokens"] + usage["output_tokens"]
            usage["cost_usd"] = float(usage.get("cost_usd", 0.0)) + call_cost

            by_model = dict(usage.get("by_model") or {})
            entry = dict(by_model.get(model_name) or {})
            entry["input_tokens"] = int(entry.get("input_tokens", 0)) + input_tokens
            entry["output_tokens"] = int(entry.get("output_tokens", 0)) + output_tokens
            entry["total_tokens"] = entry["input_tokens"] + entry["output_tokens"]
            entry["cost_usd"] = float(entry.get("cost_usd", 0.0)) + call_cost
            by_model[model_name] = entry
            usage["by_model"] = by_model

            snapshot["usage"] = usage
            run.model_snapshot = snapshot
            # JSONB mutation requires explicit flag_modified so SQLAlchemy
            # actually emits an UPDATE.
            flag_modified(run, "model_snapshot")
            await session.commit()
            return usage


def _extract_usage(
    response: LLMResult,
) -> tuple[dict[str, Any] | None, str | None]:
    """Return `(usage_metadata, model_name)` from an LLMResult, or `(None, None)`."""
    try:
        generation = response.generations[0][0]
    except IndexError:
        return None, None
    if not isinstance(generation, ChatGeneration):
        return None, None
    message = generation.message
    if not isinstance(message, AIMessage):
        return None, None
    usage = message.usage_metadata
    model_name = (message.response_metadata or {}).get("model_name")
    if not usage or not model_name:
        return None, None
    return dict(usage), str(model_name)


__all__ = ["BudgetTracker"]

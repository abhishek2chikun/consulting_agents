"""Background run worker — drives the market-entry LangGraph (M6.11).

Two entrypoints:

* :func:`start_framing` — invokes only the framing node so the user can
  see and answer the questionnaire before the (expensive) research
  pipeline kicks off. Leaves the run in ``RunStatus.questioning``.

* :func:`continue_after_framing` — persists the human-supplied answers
  and drives the full pipeline (stages → reviewers → synthesis →
  audit). It steps via ``astream()`` so a cooperative cancel
  (``Run.status -> cancelling``) takes effect at the next node
  boundary.

Both accept an injectable ``model_factory`` (one chat model per role:
``framing|research|reviewer|synthesis|audit``). When omitted the
default factory resolves real chat models from settings via
:func:`app.agents.llm.get_chat_model`.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from app.agents.budget import BudgetTracker
from app.agents.llm import get_chat_model, provider_name_for
from app.agents.market_entry.graph import build_full_graph
from app.agents.market_entry.nodes.framing import build_framing_node
from app.core.db import AsyncSessionLocal
from app.core.events import publish
from app.models import Message, MessageRole, Run, RunStatus

ModelFactory = Callable[[str], object]
ModelFactoryFactory = Callable[[], Awaitable[ModelFactory]]


def _attach_budget_tracker(
    model: object,
    *,
    run_id: uuid.UUID,
    provider: str,
) -> object:
    """Wrap `model` with a BudgetTracker callback bound to `run_id`.

    The wrapped object is a `RunnableBinding` that preserves
    `with_structured_output`, `bind_tools`, `ainvoke`, etc., so the
    stage / reviewer / synthesis / audit nodes can use it as a drop-in
    replacement for the raw chat model.
    """
    tracker = BudgetTracker(run_id=run_id, provider=provider)
    # `with_config` exists on every Runnable (BaseChatModel inherits it).
    return model.with_config(callbacks=[tracker])  # type: ignore[attr-defined]


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Default model factory
# ---------------------------------------------------------------------------


async def default_model_factory(run_id: uuid.UUID | None = None) -> ModelFactory:
    """Resolve real chat models for every role and return a sync factory.

    All five roles are resolved up-front so the synchronous
    ``model_factory(role)`` callback expected by ``build_full_graph``
    can return a cached instance per role without hitting the DB during
    graph compilation.

    When ``run_id`` is provided, each resolved model is wrapped with a
    :class:`BudgetTracker` callback bound to that run, so every chat
    call accumulates token + cost telemetry on
    ``Run.model_snapshot["usage"]`` and emits a ``usage_update`` SSE
    event. ``run_id`` is optional only for diagnostic call sites
    (``/ping``); production paths always pass it.
    """
    roles = ("framing", "research", "reviewer", "synthesis", "audit")
    cache: dict[str, object] = {}
    async with AsyncSessionLocal() as session:
        for role in roles:
            resolved: object = await get_chat_model(role, session=session)
            if run_id is not None:
                provider = provider_name_for(resolved)  # type: ignore[arg-type]
                resolved = _attach_budget_tracker(resolved, run_id=run_id, provider=provider)
            cache[role] = resolved

    def _factory(role: str) -> object:
        return cache[role]

    return _factory


# ---------------------------------------------------------------------------
# start_framing
# ---------------------------------------------------------------------------


async def start_framing(
    run_id: uuid.UUID,
    *,
    model_factory: ModelFactory | None = None,
) -> None:
    """Run only the framing node so the questionnaire is ready to render."""
    factory = model_factory or await default_model_factory(run_id)

    async with AsyncSessionLocal() as session:
        run = await session.get(Run, run_id)
        if run is None:
            return
        goal = run.goal
        document_ids = (run.model_snapshot or {}).get("document_ids", []) or []

    node = build_framing_node(model=factory("framing"))
    try:
        await node(
            {
                "run_id": str(run_id),
                "goal": goal,
                "document_ids": list(document_ids),
            }
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("framing node failed for run %s", run_id)
        await _mark_failed(run_id, reason=str(exc))
        return


# ---------------------------------------------------------------------------
# continue_after_framing
# ---------------------------------------------------------------------------


async def continue_after_framing(
    run_id: uuid.UUID,
    answers: dict[str, str],
    *,
    model_factory: ModelFactory | None = None,
) -> None:
    """Persist answers and drive the full pipeline through audit."""
    factory = model_factory or await default_model_factory(run_id)

    # 1. Persist answers as a single user-role message (audit trail).
    async with AsyncSessionLocal() as session:
        run = await session.get(Run, run_id)
        if run is None:
            return
        run.status = RunStatus.running
        session.add(
            Message(
                run_id=run_id,
                role=MessageRole.user,
                content=json.dumps(answers),
            )
        )
        await session.commit()
        goal = run.goal

    # 2. Build the framing brief from goal + answers (no second LLM call).
    framing_brief = {
        "objective": goal,
        "target_market": str(answers.get("target_market", "")) or "unspecified",
        "constraints": [],
        "questionnaire_answers": dict(answers),
    }

    # 3. Compile the graph WITHOUT the framing node and stream node-by-node
    #    so we can poll Run.status between nodes for cooperative cancel.
    graph = build_full_graph(
        model_factory=factory,
        checkpointer=None,
        include_framing=False,
    )

    initial: dict[str, Any] = {
        "run_id": str(run_id),
        "goal": goal,
        "framing": framing_brief,
    }

    cancelled = False
    try:
        async for _chunk in graph.astream(initial):
            # Each chunk is a {node_name: state_update} dict yielded after
            # a node completes. Check for cooperative cancel before
            # entering the next node.
            if await _run_is_cancelling(run_id):
                cancelled = True
                break
    except Exception as exc:
        logger.exception("graph execution failed for run %s", run_id)
        await _mark_failed(run_id, reason=str(exc))
        return

    if cancelled:
        await _mark_cancelled(run_id)
        return

    # The audit node is responsible for transitioning Run.status ->
    # completed. If it didn't (e.g. graph short-circuited via a routing
    # bug), surface that as a failure rather than silently leaving the
    # run in `running`.
    async with AsyncSessionLocal() as session:
        run = await session.get(Run, run_id)
        if run is not None and run.status == RunStatus.running:
            await _mark_failed(
                run_id,
                reason="graph completed without transitioning Run.status",
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _run_is_cancelling(run_id: uuid.UUID) -> bool:
    async with AsyncSessionLocal() as session:
        run = await session.get(Run, run_id)
        return run is not None and run.status == RunStatus.cancelling


async def _mark_cancelled(run_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        run = await session.get(Run, run_id)
        if run is None:
            return
        run.status = RunStatus.cancelled
        await session.commit()
    await publish(run_id, "run_cancelled", {"reason": "user_request"}, agent="system")


async def _mark_failed(run_id: uuid.UUID, *, reason: str) -> None:
    async with AsyncSessionLocal() as session:
        run = await session.get(Run, run_id)
        if run is None:
            return
        run.status = RunStatus.failed
        await session.commit()
    await publish(run_id, "run_failed", {"reason": reason}, agent="system")


__all__ = [
    "ModelFactory",
    "continue_after_framing",
    "default_model_factory",
    "start_framing",
]

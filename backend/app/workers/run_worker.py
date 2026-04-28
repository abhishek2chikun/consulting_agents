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

import asyncio
import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select, update

from app.agents._engine.graph import build_consulting_graph
from app.agents._engine.nodes.audit import AUDIT_PATH, REPORT_PATH
from app.agents._engine.profile import ConsultingProfile
from app.agents._engine.state import EvidenceRef, FramingBrief, GateVerdict, RunState
from app.agents.budget import BudgetTracker
from app.agents.llm import PRODUCTION_MODEL_MARKER, get_chat_model, provider_name_for
from app.agents.market_entry.nodes.framing import build_framing_node
from app.agents.tools import build_tools_factory
from app.core.config import get_settings
from app.core.db import AsyncSessionLocal
from app.core.events import publish
from app.models import Artifact, Evidence, Gate, Message, MessageRole, Run, RunStatus

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

TERMINAL_RUN_STATUSES = {
    RunStatus.completed,
    RunStatus.failed,
    RunStatus.cancelled,
}


def _assert_production_model(model: object, *, role: str) -> None:
    """Reject any model not stamped by the production registry path."""
    if getattr(model, PRODUCTION_MODEL_MARKER, False) is not True:
        raise RuntimeError(
            "default_model_factory resolved an unapproved model in the production path "
            f"for role {role!r}: {type(model).__module__}.{type(model).__name__}"
        )


# ---------------------------------------------------------------------------
# Default model factory
# ---------------------------------------------------------------------------


async def default_model_factory(run_id: uuid.UUID | None = None) -> ModelFactory:
    """Resolve real chat models for every role and return a sync factory.

    All five roles are resolved up-front so the synchronous
    ``model_factory(role)`` callback expected by graph compilation can
    return a cached instance per role without hitting the DB.

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
            _assert_production_model(resolved, role=role)
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
    profile: ConsultingProfile,
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

    node = build_framing_node(model=factory("framing"), profile=profile)
    try:
        await node(
            {
                "run_id": str(run_id),
                "goal": goal,
                "document_ids": list(document_ids),
            }
        )
    except asyncio.CancelledError:
        await _mark_cancelled(run_id)
        return
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("framing node failed for run %s", run_id)
        await _mark_failed(run_id, reason=_exception_reason(exc))
        return


# ---------------------------------------------------------------------------
# continue_after_framing
# ---------------------------------------------------------------------------


async def continue_after_framing(
    run_id: uuid.UUID,
    answers: dict[str, str],
    *,
    profile: ConsultingProfile,
    model_factory: ModelFactory | None = None,
) -> None:
    """Persist answers and drive the full pipeline through audit."""
    try:
        factory = model_factory or await default_model_factory(run_id)

        # 1. Persist answers as a single user-role message (audit trail).
        async with AsyncSessionLocal() as session:
            started_at = _utcnow()
            transition = await session.execute(
                update(Run)
                .where(
                    Run.id == run_id,
                    Run.status.in_((RunStatus.created, RunStatus.questioning)),
                )
                .values(
                    status=RunStatus.running,
                    started_at=started_at,
                    heartbeat_at=started_at,
                )
                .returning(Run.goal)
            )
            goal = transition.scalar_one_or_none()
            if goal is None:
                run = await session.get(Run, run_id)
                if run is None:
                    return
                await _mark_cancelled(run_id)
                return
            session.add(
                Message(
                    run_id=run_id,
                    role=MessageRole.user,
                    content=json.dumps(answers),
                )
            )
            await session.commit()

        # 2. Build the framing brief from goal + answers (no second LLM call).
        framing_brief: FramingBrief = {
            "objective": goal,
            "target_market": str(answers.get("target_market", "")) or "unspecified",
            "constraints": [],
            "questionnaire_answers": dict(answers),
        }

        initial: RunState = {
            "run_id": str(run_id),
            "goal": goal,
            "framing": framing_brief,
        }
        await _drive_pipeline(
            run_id,
            profile=profile,
            factory=factory,
            initial=initial,
            entry_node=None,
        )
    except asyncio.CancelledError:
        await _mark_cancelled(run_id)
        return
    except Exception as exc:
        logger.exception("graph execution failed for run %s", run_id)
        await _mark_failed(run_id, reason=_exception_reason(exc))
        return


async def retry_failed_run(
    run_id: uuid.UUID,
    *,
    profile: ConsultingProfile,
    model_factory: ModelFactory | None = None,
) -> None:
    """Resume a failed run from the first incomplete durable graph node."""
    try:
        factory = model_factory or await default_model_factory(run_id)
        retry_state = await _reconstruct_retry_state(run_id, profile=profile)
        await _drive_pipeline(
            run_id,
            profile=profile,
            factory=factory,
            initial=retry_state.initial,
            entry_node=retry_state.entry_node,
        )
    except asyncio.CancelledError:
        await _mark_cancelled(run_id)
        return
    except Exception as exc:
        logger.exception("retry execution failed for run %s", run_id)
        await _mark_failed(run_id, reason=_exception_reason(exc))
        return


async def _drive_pipeline(
    run_id: uuid.UUID,
    *,
    profile: ConsultingProfile,
    factory: ModelFactory,
    initial: RunState,
    entry_node: str | None,
) -> None:
    settings = get_settings()
    heartbeat_task: asyncio.Task[None] | None = None
    timeout_triggered = asyncio.Event()
    timeout_reason = f"timeout: exceeded {settings.run_timeout_seconds} s budget"
    run_task = asyncio.current_task()
    if run_task is None:  # pragma: no cover - asyncio always provides one here.
        raise RuntimeError("run pipeline requires an active asyncio task")
    cancelled = False
    try:
        heartbeat_task = asyncio.create_task(
            _heartbeat_loop(
                run_id,
                interval_seconds=settings.heartbeat_interval_seconds,
                timeout_seconds=settings.run_timeout_seconds,
                run_task=run_task,
                timeout_triggered=timeout_triggered,
            )
        )

        graph = build_consulting_graph(
            profile,
            model_factory=factory,
            tools_factory=build_tools_factory(run_id, AsyncSessionLocal),
            checkpointer=None,
            include_framing=False,
            entry_node=entry_node,
        )

        async for _chunk in graph.astream(initial):
            # Each chunk is a {node_name: state_update} dict yielded after
            # a node completes. Check for cooperative cancel before
            # entering the next node.
            if await _run_is_cancelling(run_id):
                cancelled = True
                break
    except asyncio.CancelledError:
        if timeout_triggered.is_set() and not await _run_is_cancelling(run_id):
            await _mark_failed(run_id, reason=timeout_reason)
        else:
            await _mark_cancelled(run_id)
        return
    except Exception as exc:
        logger.exception("graph execution failed for run %s", run_id)
        await _mark_failed(run_id, reason=_exception_reason(exc))
        return
    finally:
        if heartbeat_task is not None:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass

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
        elif run is not None and run.status in TERMINAL_RUN_STATUSES and run.completed_at is None:
            run.completed_at = _utcnow()
            await session.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RetryState:
    initial: RunState
    entry_node: str


async def preview_retry_resume_entry(run_id: uuid.UUID, *, profile: ConsultingProfile) -> str:
    """Return the node a same-run retry would start from."""
    return (await _reconstruct_retry_state(run_id, profile=profile)).entry_node


async def _reconstruct_retry_state(
    run_id: uuid.UUID,
    *,
    profile: ConsultingProfile,
) -> RetryState:
    async with AsyncSessionLocal() as session:
        run = await session.get(Run, run_id)
        if run is None:
            raise ValueError(f"run {run_id} not found")

        message = (
            await session.execute(
                select(Message)
                .where(Message.run_id == run_id, Message.role == MessageRole.user)
                .order_by(Message.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if message is None:
            raise ValueError("run has no saved questionnaire answers")
        try:
            raw_answers = json.loads(message.content)
        except json.JSONDecodeError as exc:
            raise ValueError("saved questionnaire answers are not valid JSON") from exc
        if not isinstance(raw_answers, dict):
            raise ValueError("saved questionnaire answers must be a JSON object")
        answers = {str(key): str(value) for key, value in raw_answers.items()}

        artifact_rows = list(
            (
                await session.execute(
                    select(Artifact).where(Artifact.run_id == run_id).order_by(Artifact.path)
                )
            )
            .scalars()
            .all()
        )
        evidence_rows = list(
            (
                await session.execute(
                    select(Evidence).where(Evidence.run_id == run_id).order_by(Evidence.src_id)
                )
            )
            .scalars()
            .all()
        )
        gate_rows = list(
            (
                await session.execute(
                    select(Gate)
                    .where(Gate.run_id == run_id)
                    .order_by(Gate.created_at, Gate.attempt)
                )
            )
            .scalars()
            .all()
        )

        artifacts = {row.path: row.content for row in artifact_rows}
        evidence: list[EvidenceRef] = []
        for evidence_row in evidence_rows:
            ref: EvidenceRef = {"src_id": evidence_row.src_id, "title": evidence_row.title}
            if evidence_row.url:
                ref["url"] = evidence_row.url
            evidence.append(ref)

        latest_gates: dict[str, Gate] = {}
        for gate_row in gate_rows:
            latest_gates[gate_row.stage] = gate_row

        gate_verdicts: dict[str, GateVerdict] = {}
        stage_attempts: dict[str, int] = {}
        for stage, gate_row in latest_gates.items():
            target_agents = list(gate_row.target_agents or [])
            gate_verdicts[stage] = {
                "verdict": gate_row.verdict,
                "stage": gate_row.stage,
                "attempt": gate_row.attempt,
                "gaps": list(gate_row.gaps or []),
                "target_agents": target_agents,
                "rationale": gate_row.rationale,
            }
            stage_attempts[stage] = (
                gate_row.attempt + 1 if gate_row.verdict == "reiterate" else gate_row.attempt
            )

        snapshot = run.model_snapshot or {}
        document_ids = snapshot.get("document_ids", []) or []
        initial: RunState = {
            "run_id": str(run_id),
            "goal": run.goal,
            "document_ids": [str(document_id) for document_id in document_ids],
            "framing": {
                "objective": run.goal,
                "target_market": answers.get("target_market", "") or "unspecified",
                "constraints": [],
                "questionnaire_answers": answers,
            },
            "artifacts": artifacts,
            "evidence": evidence,
            "stage_attempts": stage_attempts,
            "gate_verdicts": gate_verdicts,
            "target_agents": None,
        }
        entry_node = _resume_entry_node(profile, artifacts=artifacts, gate_verdicts=gate_verdicts)
        return RetryState(initial=initial, entry_node=entry_node)


def _resume_entry_node(
    profile: ConsultingProfile,
    *,
    artifacts: dict[str, str],
    gate_verdicts: dict[str, GateVerdict],
) -> str:
    for stage in profile.stages:
        verdict = gate_verdicts.get(stage.slug)
        if verdict is None or verdict.get("verdict") != "advance":
            return stage.node_name
    if REPORT_PATH not in artifacts:
        return "synthesis"
    if AUDIT_PATH not in artifacts:
        return "audit"
    return "audit"


async def _run_is_cancelling(run_id: uuid.UUID) -> bool:
    async with AsyncSessionLocal() as session:
        run = await session.get(Run, run_id)
        return run is not None and run.status == RunStatus.cancelling


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def _heartbeat_loop(
    run_id: uuid.UUID,
    *,
    interval_seconds: int,
    timeout_seconds: int,
    run_task: asyncio.Task[None],
    timeout_triggered: asyncio.Event,
) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        async with AsyncSessionLocal() as session:
            run = await session.get(Run, run_id)
            if run is None or run.status in TERMINAL_RUN_STATUSES:
                return
            now = _utcnow()
            if run.started_at is not None:
                elapsed_seconds = (now - run.started_at).total_seconds()
                if elapsed_seconds > timeout_seconds:
                    if run.status != RunStatus.cancelling:
                        timeout_triggered.set()
                    run_task.cancel()
                    return
            run.heartbeat_at = now
            await session.commit()


def _exception_reason(exc: BaseException) -> str:
    message = str(exc).strip()
    if message:
        return f"{type(exc).__name__}: {message}"

    cause = exc.__cause__ or exc.__context__
    if cause is not None:
        cause_message = str(cause).strip() or repr(cause)
        return f"{type(exc).__name__}: caused by {type(cause).__name__}: {cause_message}"

    return repr(exc)


async def _mark_cancelled(run_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        run = await session.get(Run, run_id)
        if run is None:
            return
        run.status = RunStatus.cancelled
        run.completed_at = _utcnow()
        await session.commit()
    await publish(run_id, "run_cancelled", {"reason": "user_request"}, agent="system")


async def _mark_failed(run_id: uuid.UUID, *, reason: str) -> None:
    async with AsyncSessionLocal() as session:
        run = await session.get(Run, run_id)
        if run is None:
            return
        run.status = RunStatus.failed
        run.completed_at = _utcnow()
        await session.commit()
    await publish(run_id, "run_failed", {"reason": reason}, agent="system")


__all__ = [
    "ModelFactory",
    "continue_after_framing",
    "default_model_factory",
    "preview_retry_resume_entry",
    "retry_failed_run",
    "start_framing",
]

"""Run streaming API routes (M5.3 SSE skeleton)."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.agents  # noqa: F401  # populate PROFILE_REGISTRY with built-in profiles
from app.agents._engine.profile import ConsultingProfile
from app.agents._engine.registry import get_profile
from app.agents.ma import run_ma_stub
from app.core.db import get_session
from app.core.events import publish
from app.core.sse import stream_run_events
from app.core.task_registry import TASK_REGISTRY
from app.models import Artifact, Evidence, Run, RunStatus
from app.schemas.runs import (
    ArtifactContentResponse,
    CreateRunRequest,
    CreateRunResponse,
    EvidenceItem,
    EvidenceListResponse,
    RunInfoResponse,
    SubmitAnswersRequest,
)
from app.services.run_service import RunService
from app.workers.run_worker import (
    ModelFactory,
    continue_after_framing,
    default_model_factory,
    start_framing,
)

router = APIRouter(prefix="/runs", tags=["runs"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]

# A "model factory builder" is a coroutine that takes a run_id and
# returns the per-role chat-model factory. We resolve the factory at
# request-handler time (not at dependency-resolution time) because the
# factory needs the run_id to attach the BudgetTracker callback.
ModelFactoryBuilder = Callable[[uuid.UUID], Awaitable[ModelFactory]]


async def get_run_model_factory_builder() -> ModelFactoryBuilder:
    """Resolve the per-run chat-model factory builder.

    Production wiring delegates to :func:`default_model_factory`, which
    resolves real chat models from the encrypted settings store and
    wraps each with a :class:`BudgetTracker` callback bound to the run.
    Tests override this dependency via
    ``app.dependency_overrides[get_run_model_factory_builder]`` to
    inject a `FakeChatModel`-backed factory and avoid network calls.
    """
    return default_model_factory


ModelFactoryBuilderDep = Annotated[ModelFactoryBuilder, Depends(get_run_model_factory_builder)]


def _profile_for_task_type(task_id: str) -> ConsultingProfile | None:
    if task_id == "ma":
        return None
    profile = get_profile(task_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unknown task_type: {task_id}",
        )
    return profile


@router.post("", response_model=CreateRunResponse, status_code=status.HTTP_201_CREATED)
async def create_run(
    body: CreateRunRequest,
    session: SessionDep,
    factory_builder: ModelFactoryBuilderDep,
) -> CreateRunResponse:
    profile = _profile_for_task_type(body.task_type)
    svc = RunService(session)
    try:
        run = await svc.create_run(
            task_type=body.task_type,
            goal=body.goal,
            document_ids=body.document_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if profile is None:
        # M&A V2 stub — no framing step, no questionnaire, and crucially
        # no LLM calls (so no model factory needed). The single-node
        # graph writes `final_report.md` and transitions the run to
        # `completed` immediately.
        TASK_REGISTRY.spawn(f"run:{run.id}", run_ma_stub(run.id))
    else:
        model_factory = await factory_builder(run.id)
        TASK_REGISTRY.spawn(
            f"run:{run.id}",
            start_framing(run.id, profile=profile, model_factory=model_factory),
        )
    return CreateRunResponse(run_id=run.id)


@router.post("/{run_id}/answers", status_code=status.HTTP_204_NO_CONTENT)
async def submit_answers(
    run_id: uuid.UUID,
    body: SubmitAnswersRequest,
    session: SessionDep,
    factory_builder: ModelFactoryBuilderDep,
) -> None:
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    profile = _profile_for_task_type(run.task_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="task_type does not accept questionnaire answers",
        )

    run.status = RunStatus.running
    await session.commit()

    model_factory = await factory_builder(run_id)
    TASK_REGISTRY.spawn(
        f"run:{run_id}",
        continue_after_framing(run_id, body.answers, profile=profile, model_factory=model_factory),
    )


@router.post("/{run_id}/cancel", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_run(run_id: uuid.UUID, session: SessionDep) -> None:
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    run.status = RunStatus.cancelling
    await session.commit()
    TASK_REGISTRY.cancel(f"run:{run_id}")
    await publish(run_id, "cancel_ack", {"status": "cancelling"}, agent="system")


@router.get("/{run_id}", response_model=RunInfoResponse)
async def get_run(run_id: uuid.UUID, session: SessionDep) -> RunInfoResponse:
    svc = RunService(session)
    run = await svc.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    paths = await svc.list_artifact_paths(run_id)
    return RunInfoResponse(
        run_id=run.id,
        task_type=run.task_id,
        goal=run.goal,
        status=run.status.value,
        artifact_paths=paths,
    )


@router.get("/{run_id}/evidence", response_model=EvidenceListResponse)
async def list_evidence(
    run_id: uuid.UUID,
    session: SessionDep,
) -> EvidenceListResponse:
    """Return every Evidence row for a run, in insertion order.

    Used by the frontend SourcesSidebar to render full source cards
    when the user clicks a `[^src_id]` chip in the report. We return
    `404` when the run itself doesn't exist (vs. an empty list when
    the run exists but has no evidence yet).
    """
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    rows = (
        (
            await session.execute(
                select(Evidence)
                .where(Evidence.run_id == run_id)
                .order_by(Evidence.accessed_at, Evidence.src_id)
            )
        )
        .scalars()
        .all()
    )
    return EvidenceListResponse(
        evidence=[
            EvidenceItem(
                src_id=r.src_id,
                kind=r.kind.value,
                url=r.url,
                title=r.title,
                snippet=r.snippet,
                provider=r.provider,
            )
            for r in rows
        ]
    )


@router.get("/{run_id}/artifacts/{artifact_path:path}", response_model=ArtifactContentResponse)
async def get_artifact(
    run_id: uuid.UUID,
    artifact_path: str,
    session: SessionDep,
) -> ArtifactContentResponse:
    row = (
        await session.execute(
            select(Artifact).where(Artifact.run_id == run_id, Artifact.path == artifact_path)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")
    return ArtifactContentResponse(path=row.path, kind=row.kind, content=row.content)


@router.get("/{run_id}/stream")
async def stream_run(
    run_id: uuid.UUID,
    last_event_id_header: str | None = Header(default=None, alias="Last-Event-ID"),
    last_event_id_query: Annotated[int | None, Query(alias="last_event_id", ge=1)] = None,
    max_events: Annotated[int | None, Query(ge=1)] = None,
) -> StreamingResponse:
    last_event_id: int | None = None
    if last_event_id_header is not None:
        try:
            last_event_id = int(last_event_id_header)
        except ValueError:
            last_event_id = None
    elif last_event_id_query is not None:
        last_event_id = last_event_id_query

    return StreamingResponse(
        stream_run_events(run_id, last_event_id=last_event_id, max_events=max_events),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


__all__ = ["router"]

"""Run streaming API routes (M5.3 SSE skeleton)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.events import publish
from app.core.sse import stream_run_events
from app.core.task_registry import TASK_REGISTRY
from app.models import Artifact, Run, RunStatus
from app.schemas.runs import (
    ArtifactContentResponse,
    CreateRunRequest,
    CreateRunResponse,
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


async def get_run_model_factory() -> ModelFactory:
    """Resolve the per-role chat-model factory used by the run worker.

    Production wiring resolves real chat models from the encrypted
    settings store. Tests override this dependency via
    `app.dependency_overrides[get_run_model_factory]` to inject a
    `FakeChatModel`-backed factory and avoid network calls / API keys.
    """
    return await default_model_factory()


ModelFactoryDep = Annotated[ModelFactory, Depends(get_run_model_factory)]


@router.post("", response_model=CreateRunResponse, status_code=status.HTTP_201_CREATED)
async def create_run(
    body: CreateRunRequest,
    session: SessionDep,
    model_factory: ModelFactoryDep,
) -> CreateRunResponse:
    svc = RunService(session)
    try:
        run = await svc.create_run(
            task_type=body.task_type,
            goal=body.goal,
            document_ids=body.document_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    TASK_REGISTRY.spawn(
        f"run:{run.id}",
        start_framing(run.id, model_factory=model_factory),
    )
    return CreateRunResponse(run_id=run.id)


@router.post("/{run_id}/answers", status_code=status.HTTP_204_NO_CONTENT)
async def submit_answers(
    run_id: uuid.UUID,
    body: SubmitAnswersRequest,
    session: SessionDep,
    model_factory: ModelFactoryDep,
) -> None:
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    run.status = RunStatus.running
    await session.commit()

    TASK_REGISTRY.spawn(
        f"run:{run_id}",
        continue_after_framing(run_id, body.answers, model_factory=model_factory),
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

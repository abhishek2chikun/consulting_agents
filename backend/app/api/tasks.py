"""Tasks catalog REST API (M3.1).

Mounts at `/tasks`. Read-only; the catalog is seeded by Alembic
migration 0004 and not user-mutable in V1. Returns rows ordered by slug
so the response is stable across deployments.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.models import TaskType
from app.schemas.tasks import TaskTypeInfo

router = APIRouter(prefix="/tasks", tags=["tasks"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_model=list[TaskTypeInfo])
async def list_tasks(session: SessionDep) -> list[TaskTypeInfo]:
    result = await session.execute(select(TaskType).order_by(TaskType.slug))
    return [
        TaskTypeInfo(
            slug=t.slug,
            name=t.name,
            description=t.description,
            enabled=t.enabled,
        )
        for t in result.scalars().all()
    ]


__all__ = ["router"]

"""Run lifecycle service methods (M5.5)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SINGLETON_USER_ID, Artifact, Run, RunStatus, TaskType
from app.services.settings_service import SettingsService


class RunService:
    """Create and mutate run lifecycle rows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_run(
        self,
        *,
        task_type: str,
        goal: str,
        document_ids: list[str],
    ) -> Run:
        task = await self._session.get(TaskType, task_type)
        if task is None:
            raise ValueError(f"Unknown task type: {task_type}")
        if not task.enabled:
            raise ValueError(f"Task type '{task_type}' is disabled")

        snapshot = await SettingsService(self._session).get_settings_snapshot()

        run = Run(
            user_id=SINGLETON_USER_ID,
            task_id=task_type,
            goal=goal,
            status=RunStatus.questioning,
            model_snapshot={
                "settings": snapshot,
                "document_ids": document_ids,
            },
        )
        self._session.add(run)
        await self._session.commit()
        await self._session.refresh(run)
        return run

    async def get_run(self, run_id: uuid.UUID) -> Run | None:
        return await self._session.get(Run, run_id)

    async def list_artifact_paths(self, run_id: uuid.UUID) -> list[str]:
        rows = (
            await self._session.execute(
                select(Artifact.path).where(Artifact.run_id == run_id).order_by(Artifact.path)
            )
        ).scalars()
        return list(rows)


__all__ = ["RunService"]

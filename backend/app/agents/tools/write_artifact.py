"""Tool to write/update a run artifact row."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any, TypedDict

from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import publish
from app.models import Artifact


class WriteArtifactResult(TypedDict):
    path: str
    kind: str
    content_length: int


def build_write_artifact(
    run_id: uuid.UUID,
    session_factory: Callable[[], AsyncSession],
) -> Any:
    @tool
    async def write_artifact(path: str, kind: str, content: str) -> dict[str, Any]:
        async with session_factory() as session:
            existing = (
                await session.execute(
                    select(Artifact).where(Artifact.run_id == run_id, Artifact.path == path)
                )
            ).scalar_one_or_none()
            if existing is None:
                session.add(Artifact(run_id=run_id, path=path, kind=kind, content=content))
            else:
                existing.kind = kind
                existing.content = content
            await session.commit()

        await publish(run_id, "artifact_update", {"path": path}, agent="tool.write_artifact")
        result = WriteArtifactResult(path=path, kind=kind, content_length=len(content))
        return dict(result)

    return write_artifact


__all__ = ["build_write_artifact"]

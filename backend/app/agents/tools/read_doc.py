"""Read a ready document's markdown representation."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any, TypedDict

from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chunk, Document, DocumentStatus


class ReadDocResult(TypedDict):
    document_id: str
    status: str
    markdown: str


def build_read_doc(session_factory: Callable[[], AsyncSession]) -> Any:
    @tool
    async def read_doc(document_id: str) -> dict[str, Any]:
        """Read markdown text assembled from indexed chunks for a ready document."""
        doc_uuid = uuid.UUID(document_id)

        async with session_factory() as session:
            doc = await session.get(Document, doc_uuid)
            if doc is None:
                raise ValueError("Document not found")
            if doc.status != DocumentStatus.ready:
                raise ValueError(f"Document {document_id} is not ready")

            rows = (
                await session.execute(
                    select(Chunk.text).where(Chunk.document_id == doc_uuid).order_by(Chunk.ord)
                )
            ).scalars()
            markdown = "\n\n".join(rows)

        result = ReadDocResult(document_id=document_id, status=doc.status.value, markdown=markdown)
        return dict(result)

    return read_doc


__all__ = ["build_read_doc"]

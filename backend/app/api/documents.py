"""Documents REST API (M3.3).

Mounts at `/documents`. Backed by `DocumentService`; only handles
multipart upload, listing, and deletion. Ingestion (parse → embed →
ready/failed) lands in M3.4+ via a background task; this router merely
creates `pending` rows.

Error mapping:
- empty filename or zero-byte upload → `400 Bad Request`
- unknown `doc_id` on DELETE → `404 Not Found`
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.task_registry import TASK_REGISTRY
from app.ingestion.worker import run_ingest
from app.schemas.documents import DocumentInfo
from app.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])


SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_document_service(session: SessionDep) -> DocumentService:
    """FastAPI dependency factory: per-request `DocumentService`."""
    return DocumentService(session)


DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]


@router.post(
    "",
    response_model=DocumentInfo,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    svc: DocumentServiceDep,
    file: Annotated[UploadFile, File(...)],
) -> DocumentInfo:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    doc = await svc.create_document(
        filename=file.filename,
        mime=file.content_type or "application/octet-stream",
        content=content,
    )
    # Kick off ingestion in the background. The handler returns 201
    # immediately with status=`pending`; the row's `status` column
    # transitions parsing → embedding → ready (or → failed) as the
    # worker progresses. The task is tracked in TASK_REGISTRY so a
    # future cancel-endpoint can find it.
    task = asyncio.create_task(run_ingest(doc.id))
    TASK_REGISTRY.register(f"ingest:{doc.id}", task)
    return DocumentInfo.model_validate(doc)


@router.get("", response_model=list[DocumentInfo])
async def list_documents(svc: DocumentServiceDep) -> list[DocumentInfo]:
    docs = await svc.list_documents()
    return [DocumentInfo.model_validate(d) for d in docs]


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(doc_id: uuid.UUID, svc: DocumentServiceDep) -> None:
    if not await svc.delete_document(doc_id):
        raise HTTPException(status_code=404, detail="Document not found")


__all__ = ["router"]

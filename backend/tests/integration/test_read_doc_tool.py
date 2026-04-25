"""Integration test for read_doc tool (M4.6)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete

from app.agents.tools.read_doc import build_read_doc
from app.core.db import AsyncSessionLocal
from app.models import SINGLETON_USER_ID, Document, DocumentStatus, Run, RunStatus


@pytest.mark.asyncio
async def test_read_doc_returns_markdown_for_ready_document() -> None:
    run_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        session.add(
            Run(
                id=run_id,
                user_id=SINGLETON_USER_ID,
                task_id="market_entry",
                goal="read_doc test",
                status=RunStatus.running,
                model_snapshot={},
            )
        )
        session.add(
            Document(
                id=doc_id,
                user_id=SINGLETON_USER_ID,
                filename="doc.md",
                mime="text/markdown",
                size=42,
                status=DocumentStatus.ready,
            )
        )
        await session.commit()

    tool = build_read_doc(AsyncSessionLocal)
    result = await tool.ainvoke({"document_id": str(doc_id)})
    assert result["document_id"] == str(doc_id)
    assert result["status"] == "ready"
    assert isinstance(result["markdown"], str)

    async with AsyncSessionLocal() as session:
        await session.execute(delete(Run).where(Run.id == run_id))
        await session.execute(delete(Document).where(Document.id == doc_id))
        await session.commit()

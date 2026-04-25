"""Integration test for run-scoped rag_search evidence registration."""

from __future__ import annotations

import uuid
from importlib import import_module

import pytest
from sqlalchemy import select

from app.agents.tools.rag_search import build_rag_search
from app.core.db import AsyncSessionLocal
from app.models import (
    SINGLETON_USER_ID,
    Chunk,
    Document,
    DocumentStatus,
    Evidence,
    Run,
    RunStatus,
)


@pytest.mark.asyncio
async def test_build_rag_search_writes_evidence_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    run_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        session.add(
            Run(
                id=run_id,
                user_id=SINGLETON_USER_ID,
                task_id="market_entry",
                goal="rag tool test",
                status=RunStatus.running,
                model_snapshot={},
            )
        )
        session.add(
            Document(
                id=doc_id,
                user_id=SINGLETON_USER_ID,
                filename="seed.pdf",
                mime="application/pdf",
                size=100,
                status=DocumentStatus.ready,
            )
        )
        await session.flush()
        session.add(
            Chunk(
                document_id=doc_id,
                ord=0,
                text="The quick brown fox jumps over the lazy dog.",
                embedding=[0.0] * 1536,
                embedding_model="seed",
            )
        )
        await session.commit()

    tool = build_rag_search(run_id, AsyncSessionLocal)

    async def _fake_embed_texts(_texts: list[str], *, session: object) -> list[list[float]]:
        _ = session
        return [[0.0] * 1536]

    rag_module = import_module("app.agents.tools.rag_search")
    monkeypatch.setattr(rag_module, "embed_texts", _fake_embed_texts)

    hits = await tool.ainvoke({"query": "quick brown fox", "k": 1})
    assert isinstance(hits, list)
    assert len(hits) == 1
    first = hits[0]
    assert "src_id" in first
    assert "title" in first
    assert "snippet" in first

    async with AsyncSessionLocal() as session:
        evidence = (
            await session.execute(select(Evidence).where(Evidence.run_id == run_id))
        ).scalars()
        rows = list(evidence)
        assert len(rows) == 1
        assert rows[0].src_id == first["src_id"]

    async with AsyncSessionLocal() as session:
        await session.execute(Run.__table__.delete().where(Run.id == run_id))
        await session.execute(Document.__table__.delete().where(Document.id == doc_id))
        await session.commit()

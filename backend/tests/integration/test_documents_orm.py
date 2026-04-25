"""Integration test: Document + Chunk ORM round-trip against real Postgres.

Requires `make db-up` and migration `0005_documents_and_chunks` applied
(`uv run alembic upgrade head`).
"""

import uuid

import numpy as np
import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import AsyncSessionLocal
from app.models import SINGLETON_USER_ID, Chunk, Document, DocumentStatus


async def test_insert_document_and_chunk_roundtrip() -> None:
    dim = get_settings().embedding_dim
    session = AsyncSessionLocal()
    doc_id = uuid.uuid4()
    try:
        doc = Document(
            id=doc_id,
            user_id=SINGLETON_USER_ID,
            filename="sample.pdf",
            mime="application/pdf",
            size=12345,
            status=DocumentStatus.pending,
        )
        session.add(doc)
        await session.flush()

        rng = np.random.default_rng(0)
        embedding = rng.random(dim).astype(float).tolist()
        chunk = Chunk(
            id=uuid.uuid4(),
            document_id=doc.id,
            ord=0,
            text="hello world",
            embedding=embedding,
            embedding_model="fake-embedder",
            metadata_={"source": "unit-test"},
        )
        session.add(chunk)
        await session.commit()

        # Fresh SELECT returns a freshly hydrated Chunk instance.
        loaded = (
            await session.execute(select(Chunk).where(Chunk.document_id == doc.id))
        ).scalar_one()
        assert loaded.ord == 0
        assert loaded.text == "hello world"
        assert loaded.embedding_model == "fake-embedder"
        assert loaded.metadata_ == {"source": "unit-test"}
        # pgvector returns numpy.ndarray on read.
        assert len(loaded.embedding) == dim
        assert pytest.approx(list(loaded.embedding)[:5], rel=1e-5) == embedding[:5]
    finally:
        # Cleanup — cascade deletes chunk via document_id FK.
        await session.execute(Document.__table__.delete().where(Document.id == doc_id))
        await session.commit()
        await session.close()

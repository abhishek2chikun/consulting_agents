"""End-to-end RAG search test (M3.7).

Reuses the M3.4 sample PDF fixture: ingests it via the live `POST
/documents` path (which schedules the M3.6 background worker), waits for
the document to reach `ready`, then calls `rag_search("quick brown fox")`
and asserts the top hit comes from the freshly-ingested document.

Requires a real `OPENAI_API_KEY` env var (used for both ingest embeddings
and the query embedding); skipped otherwise to keep CI green for
contributors without OpenAI access.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from sqlalchemy import delete

from app.agents.tools.rag_search import _rag_search_impl
from app.core.db import AsyncSessionLocal
from app.main import create_app
from app.models import Document, ProviderKey
from app.models.document import DocumentStatus
from app.services.settings_service import SettingsService

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample.pdf"


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="OPENAI_API_KEY not set; skipping live RAG integration test",
    ),
]


async def _cleanup() -> None:
    """Drop documents (cascades to chunks) and any seeded provider keys."""
    async with AsyncSessionLocal() as session:
        await session.execute(delete(Document))
        await session.execute(delete(ProviderKey))
        await session.commit()


@pytest.fixture
async def _clean_db() -> AsyncIterator[None]:
    await _cleanup()
    yield
    await _cleanup()


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _wait_until_ready(doc_id: uuid.UUID, timeout: float = 120.0) -> DocumentStatus:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        async with AsyncSessionLocal() as s:
            doc = await s.get(Document, doc_id)
            assert doc is not None
            if doc.status in (DocumentStatus.ready, DocumentStatus.failed):
                return doc.status
        await asyncio.sleep(0.5)
    raise AssertionError(f"timed out waiting for {doc_id} to reach terminal status")


async def test_rag_search_returns_relevant_chunk_after_ingest(
    client: httpx.AsyncClient,
    _clean_db: None,
) -> None:
    # 1. Configure the OpenAI key the way a real user would (settings UI).
    async with AsyncSessionLocal() as session:
        await SettingsService(session).set_provider_key("openai", os.environ["OPENAI_API_KEY"])

    # 2. Ingest the fixture PDF via the live API path (M3.3 + M3.6).
    with open(FIXTURE, "rb") as f:
        resp = await client.post(
            "/documents",
            files={"file": ("sample.pdf", f.read(), "application/pdf")},
        )
    assert resp.status_code == 201, resp.text
    doc_id = uuid.UUID(resp.json()["id"])

    status = await _wait_until_ready(doc_id)
    assert status == DocumentStatus.ready, f"ingest failed; status={status}"

    # 3. Search for a phrase known to be in page 1 of the fixture.
    hits = await _rag_search_impl("quick brown fox", k=4)
    assert len(hits) >= 1
    top = hits[0]
    # Spec contract: every hit carries text, document_id, chunk_id, score.
    assert "text" in top
    assert "document_id" in top
    assert "chunk_id" in top
    assert "score" in top
    assert "ord" in top
    # The top hit should come from the document we just ingested.
    assert top["document_id"] == str(doc_id)
    # Score sanity: cosine similarity for a verbatim-ish phrase should be
    # comfortably above zero. OpenAI embeddings are L2-normalized, so
    # `1 - cosine_distance` lands in [-1, 1].
    assert top["score"] > 0.2, f"unexpectedly low similarity: {top['score']}"

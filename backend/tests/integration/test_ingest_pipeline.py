"""End-to-end ingest pipeline test (M3.6).

Uploads a real PDF via the HTTP API and polls the document row until
the background worker reaches a terminal state. Asserts:

- terminal status is `ready` (not `failed`)
- at least one Chunk row exists
- every Chunk has a 1536-dim embedding tagged with the right model name

Requires both:
- Live Postgres (the rest of the integration suite already needs this).
- A real `OPENAI_API_KEY` env var. The test seeds it via
  SettingsService so the worker reads it through the normal code path.

If `OPENAI_API_KEY` is unset, the test is skipped — this keeps CI green
on PRs that touch ingest without forcing every contributor to provision
an OpenAI key.

Run manually with:

    cd backend && OPENAI_API_KEY=sk-... uv run pytest \\
        tests/integration/test_ingest_pipeline.py -v -s
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from sqlalchemy import delete, select

from app.core.db import AsyncSessionLocal
from app.main import create_app
from app.models import Chunk, Document, ProviderKey
from app.models.document import DocumentStatus
from app.services.settings_service import SettingsService

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample.pdf"


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="OPENAI_API_KEY not set; skipping live embedding integration test",
    ),
]


async def _cleanup() -> None:
    """Drop documents (cascades to chunks) and the seeded provider key."""
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


async def test_upload_triggers_ingest_to_ready(
    client: httpx.AsyncClient,
    _clean_db: None,
) -> None:
    # 1. Seed the OpenAI key the way a real user would (settings page).
    async with AsyncSessionLocal() as session:
        await SettingsService(session).set_provider_key("openai", os.environ["OPENAI_API_KEY"])

    # 2. Upload the fixture PDF.
    with open(FIXTURE, "rb") as fp:
        resp = await client.post(
            "/documents",
            files={"file": ("sample.pdf", fp.read(), "application/pdf")},
        )
    assert resp.status_code == 201, resp.text
    doc_id = uuid.UUID(resp.json()["id"])

    # 3. Poll until the worker reaches a terminal state. Cap at 120s
    #    because Docling's first invocation in a fresh process can
    #    download model weights (the M3.4 unit test marks itself
    #    `slow` for the same reason).
    deadline = asyncio.get_event_loop().time() + 120.0
    final_status: DocumentStatus | None = None
    final_error: str | None = None
    while asyncio.get_event_loop().time() < deadline:
        async with AsyncSessionLocal() as session:
            doc = await session.get(Document, doc_id)
            assert doc is not None
            if doc.status in (DocumentStatus.ready, DocumentStatus.failed):
                final_status = doc.status
                final_error = doc.error
                break
        await asyncio.sleep(0.5)

    assert final_status == DocumentStatus.ready, (
        f"ingest did not reach `ready` within 120s; "
        f"final status={final_status}, error={final_error}"
    )

    # 4. Verify chunks + embeddings landed in pgvector.
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Chunk).where(Chunk.document_id == doc_id).order_by(Chunk.ord)
        )
        chunks = list(result.scalars())

    assert len(chunks) >= 1, "expected at least one chunk for the sample PDF"
    for c in chunks:
        assert c.embedding is not None
        assert len(list(c.embedding)) == 1536  # text-embedding-3-small dim
        assert c.embedding_model == "text-embedding-3-small"

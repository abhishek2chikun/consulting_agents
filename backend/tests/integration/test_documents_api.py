"""Integration tests for the Documents REST API (M3.3).

Drives the FastAPI app via httpx + ASGITransport (no live network),
backed by the real Postgres instance brought up via `make db-up`.

Coverage:
- POST /documents (multipart) creates a `pending` row and writes the
  raw binary to `{UPLOAD_DIR}/{doc_id}`.
- GET /documents lists previously-uploaded documents.
- DELETE /documents/{id} removes the row and the on-disk file.
- DELETE on an unknown id returns 404.
- POST with an empty file returns 400.

Each test gets a fresh temp `UPLOAD_DIR` (via `monkeypatch.setenv` +
`get_settings.cache_clear()`) so we never touch the real
`data/uploads/`. The DB is cleaned of `documents` rows before and after
each test; the seed singleton user is left intact.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import httpx
import pytest
from sqlalchemy import delete

from app.core.config import get_settings
from app.core.db import AsyncSessionLocal
from app.main import create_app
from app.models import Document


@pytest.fixture(autouse=True)
def _isolate_upload_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Path]:
    """Point UPLOAD_DIR at a per-test tmp directory."""
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


async def _cleanup_documents() -> None:
    session = AsyncSessionLocal()
    try:
        await session.execute(delete(Document))
        await session.commit()
    finally:
        await session.close()


@pytest.fixture(autouse=True)
async def _clean_db() -> AsyncIterator[None]:
    await _cleanup_documents()
    yield
    await _cleanup_documents()


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_upload_document_creates_pending_row_and_writes_file(
    client: httpx.AsyncClient,
    _isolate_upload_dir: Path,
) -> None:
    payload = b"%PDF-1.4 fake pdf content"
    files = {"file": ("hello.pdf", payload, "application/pdf")}
    res = await client.post("/documents", files=files)

    assert res.status_code == 201
    body = res.json()
    assert body["filename"] == "hello.pdf"
    assert body["mime"] == "application/pdf"
    assert body["size"] == len(payload)
    assert body["status"] == "pending"
    assert body["error"] is None
    # Sanity: id is a UUID string.
    uuid.UUID(body["id"])

    written = _isolate_upload_dir / body["id"]
    assert written.exists()
    assert written.read_bytes() == payload


async def test_list_documents_returns_uploaded(client: httpx.AsyncClient) -> None:
    await client.post("/documents", files={"file": ("a.txt", b"a", "text/plain")})
    await client.post("/documents", files={"file": ("b.txt", b"bb", "text/plain")})

    res = await client.get("/documents")
    assert res.status_code == 200
    body = res.json()
    assert isinstance(body, list)
    assert {d["filename"] for d in body} == {"a.txt", "b.txt"}
    # Every row carries the public schema fields.
    for row in body:
        assert set(row.keys()) >= {
            "id",
            "filename",
            "mime",
            "size",
            "status",
            "error",
            "created_at",
            "updated_at",
        }


async def test_delete_document_removes_row_and_file(
    client: httpx.AsyncClient,
    _isolate_upload_dir: Path,
) -> None:
    upload = await client.post(
        "/documents",
        files={"file": ("z.txt", b"zzz", "text/plain")},
    )
    assert upload.status_code == 201
    doc_id = upload.json()["id"]
    path = _isolate_upload_dir / doc_id
    assert path.exists()

    res = await client.delete(f"/documents/{doc_id}")
    assert res.status_code == 204
    assert res.content == b""
    assert not path.exists()

    listing = await client.get("/documents")
    assert listing.status_code == 200
    assert all(d["id"] != doc_id for d in listing.json())


async def test_delete_nonexistent_returns_404(client: httpx.AsyncClient) -> None:
    res = await client.delete(f"/documents/{uuid.uuid4()}")
    assert res.status_code == 404


async def test_upload_empty_file_returns_400(client: httpx.AsyncClient) -> None:
    res = await client.post(
        "/documents",
        files={"file": ("empty.txt", b"", "text/plain")},
    )
    assert res.status_code == 400

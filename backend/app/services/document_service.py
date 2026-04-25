"""DocumentService — uploads on disk + DB rows (M3.3).

V1 is single-user: every method targets `SINGLETON_USER_ID` implicitly,
mirroring `SettingsService`. When multi-user lands the signatures will
change deliberately rather than silently routing through whatever
`user_id` callers happen to pass.

Lifecycle ordering:

- **Create:** insert row → `flush()` to populate `id` → write file →
  `commit()`. If the file write raises, the in-flight transaction is
  rolled back when the session unwinds; no orphan row.
- **Delete:** `delete()` row → `commit()` → `unlink(missing_ok=True)`.
  If the file unlink fails, the row is already gone — a small leak,
  but consistent with the V1 design preference of "DB is the source of
  truth." Acceptable for V1.

Ingestion (parsing → embedding → ready/failed) is M3.4+; this service
just creates `pending` rows and stores binaries.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import SINGLETON_USER_ID, Document, DocumentStatus


class DocumentService:
    """Manages document uploads on disk + DB rows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_document(
        self,
        *,
        filename: str,
        mime: str,
        content: bytes,
    ) -> Document:
        """Insert a `pending` Document row and write `content` to disk."""
        upload_dir = self._upload_dir()
        upload_dir.mkdir(parents=True, exist_ok=True)

        doc = Document(
            id=uuid.uuid4(),
            user_id=SINGLETON_USER_ID,
            filename=filename,
            mime=mime,
            size=len(content),
            status=DocumentStatus.pending,
        )
        self._session.add(doc)
        # flush to allocate the PK / surface FK violations before the
        # file is written; commit only happens after the bytes land on
        # disk so a write failure rolls back cleanly.
        await self._session.flush()

        target = upload_dir / str(doc.id)
        target.write_bytes(content)

        await self._session.commit()
        await self._session.refresh(doc)
        return doc

    async def list_documents(self) -> list[Document]:
        """Return all documents for the singleton user, newest first."""
        result = await self._session.execute(
            select(Document)
            .where(Document.user_id == SINGLETON_USER_ID)
            .order_by(Document.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_document(self, doc_id: uuid.UUID) -> Document | None:
        """Return the Document with `doc_id`, or `None` if absent."""
        return await self._session.get(Document, doc_id)

    async def delete_document(self, doc_id: uuid.UUID) -> bool:
        """Delete the row and its on-disk file; return False if no row."""
        doc = await self._session.get(Document, doc_id)
        if doc is None:
            return False

        path = self._upload_dir() / str(doc_id)
        await self._session.delete(doc)
        await self._session.commit()
        # File unlink AFTER the DB commit succeeds. If unlink fails the
        # row is already gone (small leak, but DB is source of truth).
        path.unlink(missing_ok=True)
        return True

    def _upload_dir(self) -> Path:
        return get_settings().upload_dir


__all__ = ["DocumentService"]

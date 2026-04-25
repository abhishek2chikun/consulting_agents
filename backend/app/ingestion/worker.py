"""Async ingest worker (M3.6).

`run_ingest(document_id)` drives one document through the pipeline:

    pending → parsing → embedding → ready
                                  ↓ (on any error)
                                failed

Notes on this state machine vs. the original M3 spec:

- The DocumentStatus enum (M3.2) defines exactly five states:
  ``pending, parsing, embedding, ready, failed``. There is no
  ``chunking`` and no ``indexed`` member, so we collapse chunking into
  the surrounding parsing step (it's a fast in-memory operation; users
  don't observe a meaningful pause there) and use ``ready`` as the
  terminal-success state instead of ``indexed``.

- The function owns its own DB sessions and **never** accepts an
  external one. It runs as a background `asyncio.Task` long after the
  request that scheduled it has closed its session, so reusing that
  session would crash with `InvalidRequestError: connection closed`.

- On an exception, the row is marked ``failed`` with a short
  ``error`` message and the function returns normally — the wrapping
  `asyncio.Task` ends up in a "completed" state, which the
  `TASK_REGISTRY` then auto-prunes. We do NOT re-raise non-cancellation
  errors so that the registry's done-callback isn't logging "Task
  exception was never retrieved" warnings on every ingest failure.

- `asyncio.CancelledError` IS re-raised after marking the row failed,
  so cooperative cancellation actually cancels the task.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

from app.core.config import get_settings
from app.core.db import AsyncSessionLocal
from app.ingestion.chunker import chunk as chunk_markdown
from app.ingestion.docling_parser import parse_to_markdown
from app.ingestion.embedder import EMBEDDING_MODEL, embed_texts
from app.models.chunk import Chunk
from app.models.document import Document, DocumentStatus

logger = logging.getLogger(__name__)


async def _set_status(
    document_id: uuid.UUID,
    status: DocumentStatus,
    error: str | None = None,
) -> None:
    """Best-effort status update on its own session.

    Silently logs (and returns) if the document has been deleted out
    from under us. Commits before returning.
    """
    async with AsyncSessionLocal() as session:
        doc = await session.get(Document, document_id)
        if doc is None:
            logger.warning("Document %s vanished mid-ingest", document_id)
            return
        doc.status = status
        if error is not None:
            doc.error = error
        await session.commit()


async def run_ingest(document_id: uuid.UUID) -> None:
    """Drive a single document through parse → chunk → embed → persist.

    Always reaches a terminal state in the DB (`ready` or `failed`)
    unless cancelled. Owns its own DB sessions; do not pass one in.
    """
    try:
        # 1. Resolve the on-disk path. The Document row carries no
        #    `path` column (M3.2 design); the file lives at
        #    `upload_dir / str(doc.id)` per DocumentService.
        async with AsyncSessionLocal() as session:
            doc = await session.get(Document, document_id)
            if doc is None:
                raise RuntimeError(f"Document {document_id} not found")
        file_path = get_settings().upload_dir / str(document_id)
        if not file_path.exists():
            raise FileNotFoundError(f"File missing on disk: {file_path}")

        # 2. Parse — Docling is blocking; bounce off the default
        #    thread pool so we don't stall the event loop.
        await _set_status(document_id, DocumentStatus.parsing)
        markdown, _meta = await asyncio.to_thread(parse_to_markdown, file_path)

        # 3. Chunk — pure-Python BPE windowing, fast enough to inline.
        #    No dedicated `chunking` enum value exists; this stays under
        #    the `parsing` status.
        chunks = chunk_markdown(markdown)
        if not chunks:
            # Empty / whitespace-only document. Nothing to embed; mark
            # ready with zero chunks rather than failing.
            await _set_status(document_id, DocumentStatus.ready)
            return

        # 4. Embed — async network IO. The session is used only to read
        #    the OpenAI API key from settings.
        await _set_status(document_id, DocumentStatus.embedding)
        async with AsyncSessionLocal() as session:
            vectors = await embed_texts([c.text for c in chunks], session=session)

        # 5. Persist all chunk rows in a single transaction.
        async with AsyncSessionLocal() as session:
            for c, v in zip(chunks, vectors, strict=True):
                row = Chunk(
                    document_id=document_id,
                    ord=c.ord,
                    text=c.text,
                    embedding=v,
                    embedding_model=EMBEDDING_MODEL,
                )
                session.add(row)
            await session.commit()

        await _set_status(document_id, DocumentStatus.ready)
    except asyncio.CancelledError:
        # Mark failed for visibility, then propagate so the task
        # actually cancels rather than silently swallowing the signal.
        await _set_status(document_id, DocumentStatus.failed, error="ingest cancelled")
        raise
    except Exception as exc:  # noqa: BLE001 — last-ditch capture
        logger.exception("Ingest failed for %s", document_id)
        await _set_status(
            document_id,
            DocumentStatus.failed,
            error=f"{type(exc).__name__}: {exc}",
        )
        # Do NOT re-raise: the row already records the failure and the
        # task should complete cleanly so TASK_REGISTRY's done-callback
        # cleans it up without an unretrieved-exception warning.


__all__ = ["run_ingest"]

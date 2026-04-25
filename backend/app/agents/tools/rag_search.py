"""LangChain `rag_search` tool — vector similarity over ingested document chunks.

This is the V1 RAG primitive used by the agent stages. It returns top-k
chunks ranked by cosine similarity to the query embedding, along with
enough metadata (document_id + chunk_id) for downstream citation.

Notes
-----
- Distance metric: pgvector's cosine distance via the SQLAlchemy
  comparator ``Chunk.embedding.cosine_distance(vec)`` (operator ``<=>``).
  pgvector returns DISTANCE (lower = closer); this tool reports
  ``score = 1 - distance`` so higher = more similar. For OpenAI's
  L2-normalized embeddings the score lands in [-1, 1] (typically [0, 1]
  for non-adversarial query/doc pairs).

- The query is embedded via ``app.ingestion.embedder.embed_texts``, the
  same path documents went through at ingest time, ensuring vector-space
  alignment.

- The HNSW index ``ix_chunks_embedding_hnsw`` (created in M3.2 with
  ``vector_cosine_ops``) is used automatically for the ORDER BY when the
  planner picks it; no explicit ``SET hnsw.ef_search`` is issued, the
  default of 40 is fine for V1 corpora.

- Tool input: a natural-language ``query`` string (and optional ``k``).
  Tool output: list of dicts; LangChain serializes them as JSON when
  packaging tool messages for the model.
"""

from __future__ import annotations

from typing import Any, TypedDict

from langchain_core.tools import tool
from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.ingestion.embedder import embed_texts
from app.models.chunk import Chunk

# Default top-k. Picked to match the V1 retrieval budget (small enough to
# keep prompt tokens bounded, large enough to surface multiple sources).
DEFAULT_K = 8


class RagHit(TypedDict):
    """Shape of a single result returned by `rag_search`."""

    text: str
    document_id: str  # UUID as str (TypedDicts ride JSON, not Python).
    chunk_id: str  # UUID as str.
    score: float  # cosine similarity in [-1, 1]; higher is better.
    ord: int  # chunk's ordinal position within its document.


async def _rag_search_impl(query: str, k: int = DEFAULT_K) -> list[RagHit]:
    """Async core of the rag_search tool.

    Exposed separately from the LangChain-decorated wrapper so tests
    (and any future Python-side caller) can invoke the implementation
    directly without going through ``StructuredTool.ainvoke``.
    """
    # Short-circuit before doing any DB / network IO.
    if not query or not query.strip():
        return []
    if k <= 0:
        return []

    async with AsyncSessionLocal() as session:
        # Embed the query (uses the OpenAI key from SettingsService —
        # same path the M3.6 worker uses for document embeddings, so the
        # vectors are in the same space).
        embeddings = await embed_texts([query], session=session)
        if not embeddings:
            return []
        q_vec = embeddings[0]

        # pgvector cosine distance via the SQLAlchemy comparator.
        # Score = 1 - distance, so higher is better.
        distance = Chunk.embedding.cosine_distance(q_vec).label("distance")
        stmt = (
            select(
                Chunk.id,
                Chunk.document_id,
                Chunk.text,
                Chunk.ord,
                distance,
            )
            .order_by(distance)
            .limit(k)
        )
        rows = (await session.execute(stmt)).all()

    return [
        RagHit(
            text=str(row.text),
            document_id=str(row.document_id),
            chunk_id=str(row.id),
            score=float(1.0 - row.distance),
            ord=int(row.ord),
        )
        for row in rows
    ]


@tool
async def rag_search(query: str, k: int = DEFAULT_K) -> list[dict[str, Any]]:
    """Search the ingested document corpus for the most relevant chunks.

    Args:
        query: Natural-language search query.
        k: Maximum number of results to return (default 8).

    Returns:
        A list of hits, each a dict with keys ``text``, ``document_id``,
        ``chunk_id``, ``ord``, and ``score`` (cosine similarity in
        [-1, 1]; higher is better). Returns an empty list for an empty
        query, ``k <= 0``, or when no documents are indexed.
    """
    hits = await _rag_search_impl(query, k=k)
    return [dict(h) for h in hits]


__all__ = ["DEFAULT_K", "RagHit", "_rag_search_impl", "rag_search"]

"""Chunk ORM model.

A `Chunk` is a contiguous span of text extracted from a `Document`,
paired with its embedding vector for similarity search. The embedding
column uses pgvector's `vector(N)` type with dimension `N` taken from
`Settings.embedding_dim` at process startup.

Caveat: `Vector(get_settings().embedding_dim)` evaluates at import time,
so changing `EMBEDDING_DIM` requires both a backend restart AND a fresh
migration (the column type is `vector(N)` with literal N).
"""

import uuid
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import get_settings
from app.core.db import Base


class Chunk(Base):
    """A text span + embedding belonging to a Document."""

    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ord: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # Vector(N) is bound at import time from settings.embedding_dim.
    embedding: Mapped[list[float]] = mapped_column(
        Vector(get_settings().embedding_dim),
        nullable=False,
    )
    embedding_model: Mapped[str] = mapped_column(String(128), nullable=False)
    # `metadata` collides with SQLAlchemy's `DeclarativeBase.metadata`
    # attribute, so the Python attr is `metadata_` while the column
    # itself is named `metadata` per the spec.
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=sql_text("'{}'::jsonb"),
    )

    __table_args__ = (
        # HNSW index for cosine-distance similarity search over embeddings.
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


__all__ = ["Chunk"]

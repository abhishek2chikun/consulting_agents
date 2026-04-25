"""Evidence ORM model (backfilled with M5.1)."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class EvidenceKind(enum.StrEnum):
    web = "web"
    doc = "doc"


class Evidence(Base):
    """Citable source row bound to a specific run."""

    __tablename__ = "evidence"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    src_id: Mapped[str] = mapped_column(String(32), nullable=False)
    kind: Mapped[EvidenceKind] = mapped_column(
        SAEnum(EvidenceKind, name="evidence_kind", native_enum=True),
        nullable=False,
    )
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("chunks.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    snippet: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    accessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (UniqueConstraint("run_id", "src_id", name="uq_evidence_run_src_id"),)


__all__ = ["Evidence", "EvidenceKind"]

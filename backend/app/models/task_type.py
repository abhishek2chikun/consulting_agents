"""Task type catalog row.

Tiny lookup table enumerating the consulting workflows the agent system
knows how to run. V1 ships exactly two rows (`market_entry`, `ma`) seeded
by the 0004 migration; the `enabled` flag gates which task types the
frontend offers in the picker (V1 enables `market_entry` only).

Slugs are the public stable identifiers — they appear in URLs and run
records — and are therefore used as the primary key directly. New task
types are added by inserting rows (typically via migration), not by
shipping new code.
"""

from sqlalchemy import Boolean, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class TaskType(Base):
    """Catalog of consulting task types the agent runtime can execute."""

    __tablename__ = "task_types"

    slug: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )


__all__ = ["TaskType"]

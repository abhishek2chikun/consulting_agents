"""Per-user key/value settings table.

Stores arbitrary JSONB values keyed by `(user_id, key)`. Schema-per-key
validation is the responsibility of the service layer (M2.4); this table
intentionally accepts any JSON-serializable shape.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class SettingKV(Base):
    """Composite-PK (user_id, key) -> JSONB value."""

    __tablename__ = "settings_kv"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


__all__ = ["SettingKV"]

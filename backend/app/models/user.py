"""User ORM model.

V1 is single-user; one seeded singleton row exists with the fixed UUID
`SINGLETON_USER_ID`. The `default=uuid.uuid4` on `id` exists so the
column can support multiple users in a future milestone without a
schema change — for V1 only the seeded row is referenced.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

SINGLETON_USER_ID: uuid.UUID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class User(Base):
    """Application user. V1 has exactly one row (the singleton)."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


__all__ = ["SINGLETON_USER_ID", "User"]

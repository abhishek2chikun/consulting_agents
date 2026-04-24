"""provider_keys

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-25

Adds the `provider_keys` table holding Fernet-encrypted third-party LLM
provider API keys, scoped per user with a unique constraint on
`(user_id, provider)`. Plaintext never lives in this column — the
service layer (`app.services.settings_service`) wraps/unwraps via
`app.core.crypto`.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "provider_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("encrypted_key", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "provider", name="uq_provider_keys_user_provider"),
    )
    op.create_index(
        op.f("ix_provider_keys_user_id"),
        "provider_keys",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_provider_keys_user_id"), table_name="provider_keys")
    op.drop_table("provider_keys")

"""users_and_settings

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-25

Creates the `users` table (V1 single-user) and `settings_kv`
(composite-PK key/value store). Seeds the singleton user row so
`settings_kv.user_id` FK references resolve immediately.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_table(
        "settings_kv",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "key"),
    )

    # Seed the V1 singleton user. ON CONFLICT keeps the migration
    # idempotent across re-runs (e.g., downgrade + upgrade cycles).
    op.execute(
        "INSERT INTO users (id, created_at) "
        "VALUES ('00000000-0000-0000-0000-000000000001', NOW()) "
        "ON CONFLICT (id) DO NOTHING"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("settings_kv")
    op.drop_table("users")

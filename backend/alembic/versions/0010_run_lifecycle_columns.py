"""run lifecycle columns

Revision ID: 0010_run_lifecycle_columns
Revises: 0009_enable_pricing
Create Date: 2026-04-28
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010_run_lifecycle_columns"
down_revision: str | Sequence[str] | None = "0009_enable_pricing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("runs", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("runs", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("runs", sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "ix_runs_status_heartbeat",
        "runs",
        ["status", "heartbeat_at"],
        unique=False,
        postgresql_where=sa.text("status = 'running'"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_runs_status_heartbeat", table_name="runs")
    op.drop_column("runs", "heartbeat_at")
    op.drop_column("runs", "completed_at")
    op.drop_column("runs", "started_at")

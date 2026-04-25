"""task_catalog

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-25

Creates the `task_types` lookup table and seeds the V1 catalog: the
`market_entry` workflow (enabled) and the `ma` stub (disabled,
placeholder for V2). The seed uses `ON CONFLICT (slug) DO NOTHING` so
the migration is idempotent across downgrade/upgrade cycles.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "task_types",
        sa.Column("slug", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    market_entry_desc = (
        "Vertical slice: framing -> research stages -> synthesis -> audit "
        "for entering a new market."
    )
    ma_desc = "Mergers & acquisitions analysis (V2 stub)."

    op.execute(
        sa.text(
            """
            INSERT INTO task_types (slug, name, description, enabled) VALUES
                ('market_entry', 'Market Entry', :me_desc, true),
                ('ma',           'M&A',          :ma_desc, false)
            ON CONFLICT (slug) DO NOTHING
            """
        ).bindparams(me_desc=market_entry_desc, ma_desc=ma_desc)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("task_types")

"""enable pricing task

Revision ID: 0009_enable_pricing
Revises: 0008_enable_profitability
Create Date: 2026-04-26
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009_enable_pricing"
down_revision: str | Sequence[str] | None = "0008_enable_profitability"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        sa.text(
            """
            INSERT INTO task_types (slug, name, description, enabled)
            VALUES ('pricing', 'Pricing',
                    'Design and validate pricing strategy and execution', true)
            ON CONFLICT (slug) DO UPDATE
            SET name = EXCLUDED.name,
                description = EXCLUDED.description,
                enabled = EXCLUDED.enabled;
            """
        )
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(sa.text("UPDATE task_types SET enabled = false WHERE slug = 'pricing'"))

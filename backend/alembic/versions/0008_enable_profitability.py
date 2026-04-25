"""enable profitability task

Revision ID: 0008_enable_profitability
Revises: 0007
Create Date: 2026-04-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008_enable_profitability"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        sa.text(
            """
            INSERT INTO task_types (slug, name, description, enabled)
            VALUES ('profitability', 'Profitability',
                    'Diagnose and improve product/segment profitability', true)
            ON CONFLICT (slug) DO UPDATE
            SET name = EXCLUDED.name,
                description = EXCLUDED.description,
                enabled = EXCLUDED.enabled;
            """
        )
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(sa.text("DELETE FROM task_types WHERE slug = 'profitability'"))

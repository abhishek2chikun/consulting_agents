"""enable_ma_task

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-25

Flips `task_types.enabled` to `true` for the `ma` slug so the
frontend task picker stops disabling the M&A option. The graph
itself is a V2-stub one-node placeholder; see
`app/agents/ma/graph.py` (M8.1).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(sa.text("UPDATE task_types SET enabled = true WHERE slug = 'ma'"))


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(sa.text("UPDATE task_types SET enabled = false WHERE slug = 'ma'"))

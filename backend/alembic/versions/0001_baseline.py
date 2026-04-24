"""baseline

Revision ID: 0001
Revises:
Create Date: 2026-04-25 02:20:11.624033

Empty baseline migration. Establishes the Alembic revision chain so
future revisions can be added with `alembic revision --autogenerate -m
"..."`. No schema yet — ORM models land in M2.1.
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass

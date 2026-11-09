"""add utc offset to users

Часовой пояс пользователя из /settings: по нему «сегодня» и время тренировки.

Revision ID: 822b4b523733
Revises: 94ccb7555006
Create Date: 2026-11-09 22:46:04.845623

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "822b4b523733"
down_revision: str | Sequence[str] | None = "94ccb7555006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column(
            "utc_offset", sa.SmallInteger(), server_default="180", nullable=False
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "utc_offset")

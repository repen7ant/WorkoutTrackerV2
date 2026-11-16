"""add program imported_at

Момент импорта программы — для экспорта «за текущую программу». У уже
загруженных программ — время миграции.

Revision ID: e870a217200b
Revises: 77fc6048ca19
Create Date: 2026-11-16 22:17:20.264795

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e870a217200b"
down_revision: str | Sequence[str] | None = "77fc6048ca19"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "programs",
        sa.Column(
            "imported_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("programs", "imported_at")

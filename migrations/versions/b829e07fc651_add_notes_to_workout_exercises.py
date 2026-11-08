"""add notes to workout exercises

Заметка к упражнению в конкретной тренировке: «не было тренажёра, делал гантели».

Revision ID: b829e07fc651
Revises: 4de80739b579
Create Date: 2026-11-08 18:01:58.784913

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b829e07fc651"
down_revision: str | Sequence[str] | None = "4de80739b579"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("workout_exercises", sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Заметки в старой схеме хранить негде, а молча терять их нельзя.
    notes = (
        op.get_bind()
        .execute(
            sa.text("SELECT count(*) FROM workout_exercises WHERE notes IS NOT NULL")
        )
        .scalar_one()
    )
    if notes:
        raise RuntimeError(
            f"{notes} exercise notes in the log; the previous schema cannot store them"
        )

    op.drop_column("workout_exercises", "notes")

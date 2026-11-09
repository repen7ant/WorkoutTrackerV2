"""add settings to users

Настройки из /settings: спрашивать ли дату и заметку при завершении тренировки,
сколько прошлых тренировок показывать при выборе упражнения.

Revision ID: 94ccb7555006
Revises: b829e07fc651
Create Date: 2026-11-09 17:38:27.613946

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "94ccb7555006"
down_revision: str | Sequence[str] | None = "b829e07fc651"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column(
            "ask_workout_date",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "ask_workout_notes",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "exercise_log_size", sa.SmallInteger(), server_default="10", nullable=False
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # настройки не жалко: тренировки они не трогают
    op.drop_column("users", "exercise_log_size")
    op.drop_column("users", "ask_workout_notes")
    op.drop_column("users", "ask_workout_date")

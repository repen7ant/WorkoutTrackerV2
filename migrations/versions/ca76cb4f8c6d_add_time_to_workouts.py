"""add time to workouts

Начало и конец тренировки по часам пользователя. У старых тренировок — NULL.

Revision ID: ca76cb4f8c6d
Revises: 822b4b523733
Create Date: 2026-11-09 22:50:23.421680

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ca76cb4f8c6d"
down_revision: str | Sequence[str] | None = "822b4b523733"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("workouts", sa.Column("start_time", sa.Time(), nullable=True))
    op.add_column("workouts", sa.Column("end_time", sa.Time(), nullable=True))
    op.create_check_constraint(
        "workouts_time_both_or_none_check",
        "workouts",
        "(start_time IS NULL) = (end_time IS NULL)",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("workouts_time_both_or_none_check", "workouts", type_="check")
    op.drop_column("workouts", "end_time")
    op.drop_column("workouts", "start_time")

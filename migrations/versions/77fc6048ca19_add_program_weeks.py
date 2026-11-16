"""add program weeks

Программа — дни × недели: неделя у плановых подходов, длина программы,
сделанные и пропущенные сессии; вместо ротации дней — следующая сессия.
Неделя у тренировки, записанной по программе.

Revision ID: 77fc6048ca19
Revises: 1e7002de7797
Create Date: 2026-11-16 21:36:27.192668

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "77fc6048ca19"
down_revision: str | Sequence[str] | None = "1e7002de7797"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "program_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("program_id", sa.Integer(), nullable=False),
        sa.Column("week", sa.SmallInteger(), nullable=False),
        sa.Column("day_position", sa.SmallInteger(), nullable=False),
        sa.Column("skipped", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["program_id"], ["programs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "program_id", "week", "day_position", name="program_sessions_once"
        ),
    )
    op.add_column(
        "program_sets",
        sa.Column("week", sa.SmallInteger(), server_default="1", nullable=False),
    )
    op.add_column(
        "programs",
        sa.Column("weeks", sa.SmallInteger(), server_default="1", nullable=False),
    )
    op.drop_column("programs", "next_position")
    op.add_column(
        "workouts", sa.Column("program_week", sa.SmallInteger(), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("workouts", "program_week")
    op.add_column(
        "programs",
        sa.Column(
            "next_position", sa.SmallInteger(), server_default="1", nullable=False
        ),
    )
    op.drop_column("programs", "weeks")
    op.drop_column("program_sets", "week")
    op.drop_table("program_sessions")

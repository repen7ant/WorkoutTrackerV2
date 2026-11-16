"""add programs

Программа тренировок от ИИ, день плана у тренировки и пожелания для ИИ
у пользователя.

Revision ID: 1e7002de7797
Revises: ca76cb4f8c6d
Create Date: 2026-11-16 18:21:52.649503

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1e7002de7797"
down_revision: str | Sequence[str] | None = "ca76cb4f8c6d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "programs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "next_position", sa.SmallInteger(), server_default="1", nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_table(
        "program_days",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("program_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("name", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["program_id"], ["programs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_program_days_program_id"), "program_days", ["program_id"], unique=False
    )
    op.create_table(
        "program_exercises",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("day_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("exercise_id", sa.Integer(), nullable=True),
        sa.Column("exercise_name", sa.String(length=128), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["day_id"], ["program_days.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["exercise_id"], ["exercises.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_program_exercises_day_id"),
        "program_exercises",
        ["day_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_program_exercises_exercise_id"),
        "program_exercises",
        ["exercise_id"],
        unique=False,
    )
    op.create_table(
        "program_sets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("program_exercise_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("weight", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("reps", sa.SmallInteger(), nullable=True),
        sa.Column("seconds", sa.SmallInteger(), nullable=True),
        sa.CheckConstraint(
            "(reps IS NULL) <> (seconds IS NULL)",
            name="program_sets_reps_or_seconds_check",
        ),
        sa.ForeignKeyConstraint(
            ["program_exercise_id"], ["program_exercises.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_program_sets_program_exercise_id"),
        "program_sets",
        ["program_exercise_id"],
        unique=False,
    )
    op.add_column("users", sa.Column("ai_wishes", sa.Text(), nullable=True))
    op.add_column(
        "workouts", sa.Column("program_day", sa.String(length=32), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("workouts", "program_day")
    op.drop_column("users", "ai_wishes")
    op.drop_index(
        op.f("ix_program_sets_program_exercise_id"), table_name="program_sets"
    )
    op.drop_table("program_sets")
    op.drop_index(
        op.f("ix_program_exercises_exercise_id"), table_name="program_exercises"
    )
    op.drop_index(op.f("ix_program_exercises_day_id"), table_name="program_exercises")
    op.drop_table("program_exercises")
    op.drop_index(op.f("ix_program_days_program_id"), table_name="program_days")
    op.drop_table("program_days")
    op.drop_table("programs")

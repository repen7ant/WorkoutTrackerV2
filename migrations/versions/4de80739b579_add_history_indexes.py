"""add history indexes

Графики Mini App читают всю историю упражнения — без индексов это чтение
замедляется по мере роста базы.

Revision ID: 4de80739b579
Revises: cd4617a8ea7d
Create Date: 2026-10-31 15:25:01.045521

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4de80739b579"
down_revision: str | Sequence[str] | None = "cd4617a8ea7d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index("ix_workouts_user_id", "workouts", ["user_id"])
    op.create_index(
        "ix_workout_exercises_workout_id", "workout_exercises", ["workout_id"]
    )
    op.create_index(
        "ix_workout_exercises_exercise_id", "workout_exercises", ["exercise_id"]
    )
    op.create_index("ix_sets_workout_exercise_id", "sets", ["workout_exercise_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_sets_workout_exercise_id", table_name="sets")
    op.drop_index("ix_workout_exercises_exercise_id", table_name="workout_exercises")
    op.drop_index("ix_workout_exercises_workout_id", table_name="workout_exercises")
    op.drop_index("ix_workouts_user_id", table_name="workouts")

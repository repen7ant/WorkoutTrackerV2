"""keep exercise name in workouts

Упражнение можно удалить из каталога, а тренировки с ним остаются: название
копируется в workout_exercises, ссылка на каталог при удалении обнуляется.

Revision ID: b7c4e2a91f30
Revises: 363413e23063
Create Date: 2026-09-23 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7c4e2a91f30"
down_revision: str | Sequence[str] | None = "363413e23063"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # сначала nullable: у уже записанных тренировок названия ещё нет
    op.add_column(
        "workout_exercises",
        sa.Column("exercise_name", sa.String(length=128), nullable=True),
    )
    op.execute(
        """
        UPDATE workout_exercises AS we
        SET exercise_name = e.name
        FROM exercises AS e
        WHERE e.id = we.exercise_id
        """
    )
    op.alter_column("workout_exercises", "exercise_name", nullable=False)

    op.alter_column(
        "workout_exercises", "exercise_id", existing_type=sa.Integer(), nullable=True
    )
    op.drop_constraint(
        "workout_exercises_exercise_id_fkey", "workout_exercises", type_="foreignkey"
    )
    op.create_foreign_key(
        "workout_exercises_exercise_id_fkey",
        "workout_exercises",
        "exercises",
        ["exercise_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Записи удалённых упражнений в старую схему не вернуть: exercise_id там
    # обязателен. Молча удалять чужую историю откат не должен.
    orphans = (
        op.get_bind()
        .execute(
            sa.text("SELECT count(*) FROM workout_exercises WHERE exercise_id IS NULL")
        )
        .scalar_one()
    )
    if orphans:
        raise RuntimeError(
            f"{orphans} workout entries reference deleted exercises; "
            "the previous schema cannot store them"
        )

    op.drop_constraint(
        "workout_exercises_exercise_id_fkey", "workout_exercises", type_="foreignkey"
    )
    op.create_foreign_key(
        "workout_exercises_exercise_id_fkey",
        "workout_exercises",
        "exercises",
        ["exercise_id"],
        ["id"],
    )
    op.alter_column(
        "workout_exercises", "exercise_id", existing_type=sa.Integer(), nullable=False
    )
    op.drop_column("workout_exercises", "exercise_name")

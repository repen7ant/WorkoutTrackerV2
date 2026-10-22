"""add timed sets

Подход хранит либо повторения, либо время в секундах (планка, farmer's walk) —
ровно одно из двух.

Revision ID: cd4617a8ea7d
Revises: b7c4e2a91f30
Create Date: 2026-10-22 18:48:28.106150

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cd4617a8ea7d"
down_revision: str | Sequence[str] | None = "b7c4e2a91f30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("sets", sa.Column("seconds", sa.SmallInteger(), nullable=True))
    op.alter_column("sets", "reps", existing_type=sa.SmallInteger(), nullable=True)
    op.create_check_constraint(
        "sets_reps_or_seconds_check", "sets", "(reps IS NULL) <> (seconds IS NULL)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Подходы на время в старую схему не вернуть: reps там обязателен.
    timed = (
        op.get_bind()
        .execute(sa.text("SELECT count(*) FROM sets WHERE seconds IS NOT NULL"))
        .scalar_one()
    )
    if timed:
        raise RuntimeError(
            f"{timed} timed sets in the log; the previous schema cannot store them"
        )

    op.drop_constraint("sets_reps_or_seconds_check", "sets", type_="check")
    op.alter_column("sets", "reps", existing_type=sa.SmallInteger(), nullable=False)
    op.drop_column("sets", "seconds")

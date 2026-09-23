"""
Всё, что каталог отдаёт другим модулям.

Тренировки, история и экспорт узнают названия и мышцы упражнений только
отсюда, а не из таблиц каталога
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.catalog.models import Exercise, ExerciseMuscle, Muscle
from bot.catalog.repository import ExerciseRepository


@dataclass(frozen=True)
class ExerciseInfo:
    id: int
    name: str
    muscles: tuple[str, ...] = ()


class Catalog:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def search(
        self, query: str, user_id: int, limit: int = 20
    ) -> tuple[list[ExerciseInfo], int]:
        exercises, total = await ExerciseRepository(self.session).search_by_name(
            query, user_id, limit
        )
        return [ExerciseInfo(id=ex.id, name=ex.name) for ex in exercises], total

    async def get_visible(self, exercise_id: int, user_id: int) -> ExerciseInfo | None:
        """Упражнение, если пользователь может им пользоваться: своё или общее."""
        ex = await ExerciseRepository(self.session).get_visible(exercise_id, user_id)
        return ExerciseInfo(id=ex.id, name=ex.name) if ex else None

    async def visible_ids(self, exercise_ids: set[int], user_id: int) -> set[int]:
        """Те из exercise_ids, что доступны пользователю."""
        if not exercise_ids:
            return set()
        result = await self.session.execute(
            select(Exercise.id).where(
                Exercise.id.in_(exercise_ids), Exercise.visible_to(user_id)
            )
        )
        return set(result.scalars().all())

    async def describe(
        self, exercise_ids: set[int], with_muscles: bool = False
    ) -> dict[int, ExerciseInfo]:
        """
        Названия (и, если нужно, мышцы по алфавиту) уже записанных упражнений.

        Доступ здесь не проверяется: ids приходят из тренировок самого
        пользователя, а упражнение, однажды попавшее в тренировку, остаётся
        частью его истории.
        """
        if not exercise_ids:
            return {}
        result = await self.session.execute(
            select(Exercise.id, Exercise.name).where(Exercise.id.in_(exercise_ids))
        )
        names = dict(result.tuples().all())

        muscles: dict[int, list[str]] = {}
        if with_muscles:
            result = await self.session.execute(
                select(ExerciseMuscle.exercise_id, Muscle.name)
                .join(Muscle, Muscle.id == ExerciseMuscle.muscle_id)
                .where(ExerciseMuscle.exercise_id.in_(exercise_ids))
                .order_by(Muscle.name)
            )
            for exercise_id, name in result.tuples().all():
                muscles.setdefault(exercise_id, []).append(name)

        return {
            ex_id: ExerciseInfo(
                id=ex_id, name=name, muscles=tuple(muscles.get(ex_id, ()))
            )
            for ex_id, name in names.items()
        }

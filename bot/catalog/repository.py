from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.catalog.models import Exercise, ExerciseMuscle, Muscle


class ExerciseRepository:
    """Таблицы каталога — и только они: тренировки сюда не заглядывают."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def search_by_name(
        self, query: str, user_id: int, limit: int = 20
    ) -> tuple[list[Exercise], int]:
        """Совпадения и их общее число: по короткому запросу их могут быть сотни,
        а Telegram не покажет ни такую клавиатуру, ни такое сообщение."""
        filters = (Exercise.visible_to(user_id), Exercise.name.ilike(f"%{query}%"))

        total_result = await self.session.execute(
            select(func.count(Exercise.id)).where(*filters)
        )
        total = total_result.scalar_one()

        result = await self.session.execute(
            select(Exercise)
            .options(selectinload(Exercise.muscles))
            .where(*filters)
            .order_by(Exercise.name)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def get_visible(self, exercise_id: int, user_id: int) -> Exercise | None:
        """Упражнение, доступное этому пользователю: своё или общее."""
        result = await self.session.execute(
            select(Exercise).where(
                Exercise.id == exercise_id, Exercise.visible_to(user_id)
            )
        )
        return result.scalar_one_or_none()

    async def get_own(self, exercise_id: int, user_id: int) -> Exercise | None:
        """Только личное упражнение: общие удалять нельзя."""
        result = await self.session.execute(
            select(Exercise).where(
                Exercise.id == exercise_id, Exercise.owned_by(user_id)
            )
        )
        return result.scalar_one_or_none()

    async def add(
        self, name: str, user_id: int, muscle_names: list[str]
    ) -> Exercise | None:
        """None, если упражнение с таким названием уже доступно пользователю."""
        existing = await self.session.execute(
            select(Exercise.id).where(
                Exercise.name.ilike(name), Exercise.visible_to(user_id)
            )
        )
        if existing.first() is not None:
            return None

        exercise = Exercise(name=name, user_id=user_id)
        self.session.add(exercise)
        await self.session.flush()

        for muscle_name in muscle_names:
            result = await self.session.execute(
                select(Muscle).where(
                    Muscle.name.ilike(muscle_name), Muscle.visible_to(user_id)
                )
            )
            muscle = result.scalar_one_or_none()
            if muscle is None:
                muscle = Muscle(name=muscle_name, user_id=user_id)
                self.session.add(muscle)
                await self.session.flush()
            link = ExerciseMuscle(exercise_id=exercise.id, muscle_id=muscle.id)
            self.session.add(link)

        await self.session.commit()
        return exercise

    async def filter_by_muscle_id(self, muscle_id: int, user_id: int) -> list[Exercise]:
        result = await self.session.execute(
            select(Exercise)
            .options(selectinload(Exercise.muscles))
            .join(ExerciseMuscle)
            .where(Exercise.visible_to(user_id), ExerciseMuscle.muscle_id == muscle_id)
            .order_by(Exercise.name)
        )
        return list(result.scalars().all())

    async def delete(self, exercise_id: int, user_id: int) -> bool:
        exercise = await self.get_own(exercise_id, user_id)
        if exercise is None:
            return False
        await self.session.delete(exercise)
        await self.cleanup_orphan_muscles()
        await self.session.commit()
        return True

    async def get_page(
        self, page: int, user_id: int, per_page: int = 20
    ) -> tuple[list[Exercise], int]:
        total_result = await self.session.execute(
            select(func.count(Exercise.id)).where(Exercise.visible_to(user_id))
        )
        total = total_result.scalar_one()
        total_pages = max(1, (total + per_page - 1) // per_page)

        result = await self.session.execute(
            select(Exercise)
            .options(selectinload(Exercise.muscles))
            .where(Exercise.visible_to(user_id))
            .order_by(Exercise.name)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        return list(result.scalars().all()), total_pages

    async def get_user_exercises(self, user_id: int) -> list[Exercise]:
        result = await self.session.execute(
            select(Exercise).where(Exercise.owned_by(user_id)).order_by(Exercise.name)
        )
        return list(result.scalars().all())

    async def get_all_muscles(self, user_id: int) -> list[Muscle]:
        result = await self.session.execute(
            select(Muscle).where(Muscle.visible_to(user_id)).order_by(Muscle.name)
        )
        return list(result.scalars().all())

    async def cleanup_orphan_muscles(self) -> None:
        result = await self.session.execute(
            select(Muscle).where(~Muscle.id.in_(select(ExerciseMuscle.muscle_id)))
        )
        orphans = result.scalars().all()
        for muscle in orphans:
            await self.session.delete(muscle)

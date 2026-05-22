from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.models.exercise_muscles import ExerciseMuscle
from bot.models.exercises import Exercise
from bot.models.muscles import Muscle
from bot.models.sets import Set
from bot.models.workout_exercises import WorkoutExercise
from bot.models.workouts import Workout


class ExerciseRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def search_by_name(self, query: str, user_id: int) -> list[Exercise]:
        base_filter = Exercise.user_id.is_(None) | (Exercise.user_id == user_id)
        result = await self.session.execute(
            select(Exercise)
            .options(selectinload(Exercise.muscles))
            .where(base_filter, Exercise.name.ilike(f"%{query}%"))
        )
        return list(result.scalars().all())

    async def add(self, name: str, user_id: int, muscle_names: list[str]) -> Exercise:
        exercise = Exercise(name=name, user_id=user_id)
        self.session.add(exercise)
        await self.session.flush()

        for muscle_name in muscle_names:
            result = await self.session.execute(
                select(Muscle).where(
                    Muscle.name.ilike(muscle_name),
                    Muscle.user_id.is_(None) | (Muscle.user_id == user_id),
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
        base_filter = Exercise.user_id.is_(None) | (Exercise.user_id == user_id)
        result = await self.session.execute(
            select(Exercise)
            .options(selectinload(Exercise.muscles))
            .join(ExerciseMuscle)
            .where(base_filter, ExerciseMuscle.muscle_id == muscle_id)
        )
        return list(result.scalars().all())

    async def delete(self, exercise_id: int, user_id: int) -> bool:
        result = await self.session.execute(
            select(Exercise).where(
                Exercise.id == exercise_id,
                Exercise.user_id == user_id,
            )
        )
        exercise = result.scalar_one_or_none()
        if exercise is None:
            return False
        await self.session.delete(exercise)
        await self.cleanup_orphan_muscles()
        await self.session.commit()
        return True

    async def get_page(
        self, page: int, user_id: int, per_page: int = 20
    ) -> tuple[list[tuple[Exercise, list[Muscle]]], int]:
        base_filter = Exercise.user_id.is_(None) | (Exercise.user_id == user_id)

        total_result = await self.session.execute(
            select(func.count(Exercise.id)).where(base_filter)
        )
        total = total_result.scalar_one()
        total_pages = max(1, (total + per_page - 1) // per_page)

        result = await self.session.execute(
            select(Exercise)
            .options(selectinload(Exercise.muscles))
            .where(base_filter)
            .order_by(Exercise.name)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        exercises = result.scalars().all()
        return [(ex, ex.muscles) for ex in exercises], total_pages

    async def get_user_exercises(self, user_id: int) -> list[Exercise]:
        result = await self.session.execute(
            select(Exercise).where(Exercise.user_id == user_id)
        )
        return list(result.scalars().all())

    async def get_all_muscles(self, user_id: int) -> list[Muscle]:
        result = await self.session.execute(
            select(Muscle).where(Muscle.user_id.is_(None) | (Muscle.user_id == user_id))
        )
        return list(result.scalars().all())

    async def cleanup_orphan_muscles(self) -> None:
        result = await self.session.execute(
            select(Muscle).where(~Muscle.id.in_(select(ExerciseMuscle.muscle_id)))
        )
        orphans = result.scalars().all()
        for muscle in orphans:
            await self.session.delete(muscle)

    async def get_exercise_log(
        self, exercise_id: int, user_id: int, limit: int = 20
    ) -> list[dict]:
        result = await self.session.execute(
            select(Workout, WorkoutExercise, Set)
            .join(WorkoutExercise, WorkoutExercise.workout_id == Workout.id)
            .join(Set, Set.workout_exercise_id == WorkoutExercise.id)
            .where(
                WorkoutExercise.exercise_id == exercise_id,
                Workout.user_id == user_id,
            )
            .order_by(Workout.date.asc())
            .limit(limit)
        )
        rows = result.all()

        sessions: dict[int, dict] = {}
        for workout, we, s in rows:
            if workout.id not in sessions:
                sessions[workout.id] = {
                    "date": workout.date,
                    "notes": workout.notes,
                    "sets": [],
                }
            sessions[workout.id]["sets"].append(
                {
                    "weight": s.weight,
                    "reps": s.reps,
                }
            )

        return list(sessions.values())

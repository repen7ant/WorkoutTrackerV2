from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.exercises import Exercise
from bot.models.sets import Set
from bot.models.workout_exercises import WorkoutExercise
from bot.models.workouts import Workout


class WorkoutRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_workout(
        self,
        user_id: int,
        workout_date: date,
        notes: str | None,
        exercises: list[dict],
    ) -> Workout:
        workout = Workout(user_id=user_id, date=workout_date, notes=notes)
        self.session.add(workout)
        await self.session.flush()

        for position, exercise_data in enumerate(exercises, start=1):
            we = WorkoutExercise(
                workout_id=workout.id,
                exercise_id=exercise_data["exercise_id"],
                position=position,
            )
            self.session.add(we)
            await self.session.flush()

            for set_data in exercise_data["sets"]:
                s = Set(
                    workout_exercise_id=we.id,
                    reps=set_data["reps"],
                    weight=set_data["weight"],
                )
                self.session.add(s)

        await self.session.commit()
        return workout

    async def get_workouts_page(
        self, user_id: int, page: int, per_page: int = 10
    ) -> tuple[list[Workout], int]:
        total_result = await self.session.execute(
            select(func.count(Workout.id)).where(Workout.user_id == user_id)
        )
        total = total_result.scalar_one()
        total_pages = max(1, (total + per_page - 1) // per_page)

        result = await self.session.execute(
            select(Workout)
            .where(Workout.user_id == user_id)
            .order_by(Workout.date.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        return list(result.scalars().all()), total_pages

    async def get_workout_detail(self, workout_id: int, user_id: int) -> list[dict]:
        result = await self.session.execute(
            select(WorkoutExercise, Exercise, Set)
            .join(Exercise, Exercise.id == WorkoutExercise.exercise_id)
            .join(Set, Set.workout_exercise_id == WorkoutExercise.id)
            .where(WorkoutExercise.workout_id == workout_id)
            .order_by(WorkoutExercise.position, Set.id)
        )
        rows = result.all()

        exercises: dict[int, dict] = {}
        for we, ex, s in rows:
            if we.id not in exercises:
                exercises[we.id] = {
                    "exercise_name": ex.name,
                    "sets": [],
                }
            exercises[we.id]["sets"].append(
                {
                    "weight": s.weight,
                    "reps": s.reps,
                }
            )
        return list(exercises.values())

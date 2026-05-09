from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

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
        async with self.session.begin():
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

        return workout

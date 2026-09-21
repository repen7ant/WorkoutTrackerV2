from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.exercise_muscles import ExerciseMuscle
from bot.models.exercises import Exercise
from bot.models.muscles import Muscle
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
            # id как тай-брейк: без него тренировки одной даты прыгают между страницами
            .order_by(Workout.date.desc(), Workout.id.desc())
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

    async def get_workouts_for_export(
        self, user_id: int, since: date | None
    ) -> list[dict]:
        """Все тренировки пользователя с упражнениями, мышцами и подходами.

        Отсортированы от старых к новым; внутри тренировки упражнения идут
        в порядке выполнения, подходы — в порядке ввода.
        """
        filters = [Workout.user_id == user_id]
        if since is not None:
            filters.append(Workout.date >= since)

        result = await self.session.execute(
            select(Workout, WorkoutExercise, Exercise, Set)
            .join(WorkoutExercise, WorkoutExercise.workout_id == Workout.id)
            .join(Exercise, Exercise.id == WorkoutExercise.exercise_id)
            .join(Set, Set.workout_exercise_id == WorkoutExercise.id)
            .where(*filters)
            .order_by(
                Workout.date.asc(),
                Workout.id.asc(),
                WorkoutExercise.position.asc(),
                Set.id.asc(),
            )
        )
        rows = result.all()
        if not rows:
            return []

        muscles = await self._get_exercise_muscles({ex.id for _, _, ex, _ in rows})

        workouts: dict[int, dict] = {}
        entries: dict[int, dict] = {}
        for workout, we, exercise, s in rows:
            if workout.id not in workouts:
                workouts[workout.id] = {
                    "date": workout.date,
                    "notes": workout.notes,
                    "exercises": [],
                }
            if we.id not in entries:
                entries[we.id] = {
                    "name": exercise.name,
                    "muscles": muscles.get(exercise.id, []),
                    "sets": [],
                }
                workouts[workout.id]["exercises"].append(entries[we.id])
            entries[we.id]["sets"].append({"weight": s.weight, "reps": s.reps})

        return list(workouts.values())

    async def _get_exercise_muscles(
        self, exercise_ids: set[int]
    ) -> dict[int, list[str]]:
        result = await self.session.execute(
            select(ExerciseMuscle.exercise_id, Muscle.name)
            .join(Muscle, Muscle.id == ExerciseMuscle.muscle_id)
            .where(ExerciseMuscle.exercise_id.in_(exercise_ids))
            .order_by(Muscle.name)
        )
        muscles: dict[int, list[str]] = {}
        for exercise_id, name in result.all():
            muscles.setdefault(exercise_id, []).append(name)
        return muscles

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.workouts.domain import (
    LoggedExercise,
    LoggedWorkout,
    SetEntry,
    WorkoutRecord,
)
from bot.workouts.models import Set, Workout, WorkoutExercise


class WorkoutRepository:
    """
    Единственный, кто знает таблицы тренировок.

    Пишет готовую WorkoutRecord как есть — правила уже проверены при её
    сборке. Читает всегда в одну форму, LoggedWorkout: как её показать или
    выгрузить, решают история и экспорт у себя.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, record: WorkoutRecord, names: dict[int, str]) -> int:
        """names — названия упражнений по id: они сохраняются вместе с
        тренировкой и переживают удаление упражнения из каталога."""
        workout = Workout(user_id=record.user_id, date=record.date, notes=record.notes)
        self.session.add(workout)
        await self.session.flush()

        for position, entry in record.positioned():
            we = WorkoutExercise(
                workout_id=workout.id,
                exercise_id=entry.exercise_id,
                exercise_name=names[entry.exercise_id],
                position=position,
            )
            self.session.add(we)
            await self.session.flush()
            self.session.add_all(
                Set(workout_exercise_id=we.id, reps=s.reps, weight=s.weight)
                for s in entry.sets
            )

        await self.session.flush()
        return workout.id

    async def page(
        self, user_id: int, page: int, per_page: int = 10
    ) -> tuple[list[LoggedWorkout], int]:
        """Страница тренировок, новые сверху, без упражнений."""
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
        workouts = [
            LoggedWorkout(id=w.id, date=w.date, notes=w.notes, exercises=[])
            for w in result.scalars().all()
        ]
        return workouts, total_pages

    async def get(self, workout_id: int, user_id: int) -> LoggedWorkout | None:
        workouts = await self._load(
            Workout.id == workout_id, Workout.user_id == user_id
        )
        return workouts[0] if workouts else None

    async def since(self, user_id: int, since: date | None) -> list[LoggedWorkout]:
        """Все тренировки пользователя с даты since (None — за всё время),
        от старых к новым."""
        filters = [Workout.user_id == user_id]
        if since is not None:
            filters.append(Workout.date >= since)
        return await self._load(*filters)

    async def with_exercise(
        self, exercise_id: int, user_id: int, limit: int = 10
    ) -> list[LoggedWorkout]:
        """Последние limit тренировок с этим упражнением, от старых к новым;
        в каждой — только оно."""
        recent = (
            select(Workout.id)
            .where(
                Workout.user_id == user_id,
                Workout.id.in_(
                    select(WorkoutExercise.workout_id).where(
                        WorkoutExercise.exercise_id == exercise_id
                    )
                ),
            )
            .order_by(Workout.date.desc(), Workout.id.desc())
            .limit(limit)
        )
        return await self._load(
            Workout.id.in_(recent), WorkoutExercise.exercise_id == exercise_id
        )

    async def _load(self, *filters) -> list[LoggedWorkout]:
        """Тренировки от старых к новым; упражнения — в порядке выполнения,
        подходы — в порядке ввода."""
        result = await self.session.execute(
            select(Workout, WorkoutExercise, Set)
            .join(WorkoutExercise, WorkoutExercise.workout_id == Workout.id)
            .join(Set, Set.workout_exercise_id == WorkoutExercise.id)
            .where(*filters)
            .order_by(
                Workout.date.asc(),
                Workout.id.asc(),
                WorkoutExercise.position.asc(),
                Set.id.asc(),
            )
        )

        workouts: dict[int, LoggedWorkout] = {}
        entries: dict[int, LoggedExercise] = {}
        for workout, we, s in result.tuples().all():
            if workout.id not in workouts:
                workouts[workout.id] = LoggedWorkout(
                    id=workout.id, date=workout.date, notes=workout.notes, exercises=[]
                )
            if we.id not in entries:
                entries[we.id] = LoggedExercise(
                    exercise_id=we.exercise_id, name=we.exercise_name, sets=[]
                )
                workouts[workout.id].exercises.append(entries[we.id])
            entries[we.id].sets.append(SetEntry(weight=s.weight, reps=s.reps))
        return list(workouts.values())

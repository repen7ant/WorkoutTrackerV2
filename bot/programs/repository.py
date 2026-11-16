from dataclasses import dataclass

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.catalog.api import ExerciseInfo
from bot.programs.domain import ProgramPlan
from bot.programs.models import Program, ProgramDay, ProgramExercise, ProgramSet
from bot.workouts.domain import SetEntry


@dataclass(frozen=True)
class StoredExercise:
    exercise_id: int | None  # None — упражнение удалено из каталога
    name: str
    notes: str | None
    sets: list[SetEntry]


@dataclass(frozen=True)
class StoredDay:
    position: int
    name: str
    exercises: list[StoredExercise]


@dataclass(frozen=True)
class StoredProgram:
    id: int
    next_position: int
    days: list[StoredDay]


class ProgramRepository:
    """Единственный, кто знает таблицы программ."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, user_id: int) -> StoredProgram | None:
        program = await self.session.scalar(
            select(Program).where(Program.user_id == user_id)
        )
        if program is None:
            return None
        result = await self.session.execute(
            select(ProgramDay, ProgramExercise, ProgramSet)
            .join(ProgramExercise, ProgramExercise.day_id == ProgramDay.id)
            .join(ProgramSet, ProgramSet.program_exercise_id == ProgramExercise.id)
            .where(ProgramDay.program_id == program.id)
            .order_by(
                ProgramDay.position, ProgramExercise.position, ProgramSet.position
            )
        )
        days: dict[int, StoredDay] = {}
        exercises: dict[int, StoredExercise] = {}
        for day, ex, s in result.tuples().all():
            if day.id not in days:
                days[day.id] = StoredDay(
                    position=day.position, name=day.name, exercises=[]
                )
            if ex.id not in exercises:
                exercises[ex.id] = StoredExercise(
                    exercise_id=ex.exercise_id,
                    name=ex.exercise_name,
                    notes=ex.notes,
                    sets=[],
                )
                days[day.id].exercises.append(exercises[ex.id])
            exercises[ex.id].sets.append(
                SetEntry(weight=s.weight, reps=s.reps, seconds=s.seconds)
            )
        return StoredProgram(
            id=program.id, next_position=program.next_position, days=list(days.values())
        )

    async def replace(
        self, user_id: int, plan: ProgramPlan, exercises: dict[str, ExerciseInfo]
    ) -> None:
        """
        Новая программа вместо старой. exercises — упражнение каталога по
        casefold() названия из плана; название сохраняется каталожное.
        """
        # дни, упражнения и подходы удаляет каскад внешних ключей
        await self.delete(user_id)
        program = Program(user_id=user_id, next_position=1)
        self.session.add(program)
        await self.session.flush()
        for day_pos, day in enumerate(plan.days, start=1):
            day_row = ProgramDay(program_id=program.id, position=day_pos, name=day.name)
            self.session.add(day_row)
            await self.session.flush()
            for ex_pos, ex in enumerate(day.exercises, start=1):
                info = exercises[ex.name.casefold()]
                ex_row = ProgramExercise(
                    day_id=day_row.id,
                    position=ex_pos,
                    exercise_id=info.id,
                    exercise_name=info.name,
                    notes=ex.notes,
                )
                self.session.add(ex_row)
                await self.session.flush()
                self.session.add_all(
                    ProgramSet(
                        program_exercise_id=ex_row.id,
                        position=set_pos,
                        weight=s.weight,
                        reps=s.reps,
                        seconds=s.seconds,
                    )
                    for set_pos, s in enumerate(ex.sets, start=1)
                )
        await self.session.flush()

    async def delete(self, user_id: int) -> bool:
        result = await self.session.execute(
            delete(Program).where(Program.user_id == user_id)
        )
        return result.rowcount > 0

    async def set_next_position(
        self, user_id: int, program_id: int, position: int
    ) -> bool:
        """False — программу уже заменили или удалили."""
        result = await self.session.execute(
            update(Program)
            .where(Program.id == program_id, Program.user_id == user_id)
            .values(next_position=position)
        )
        return result.rowcount > 0

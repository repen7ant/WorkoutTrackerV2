from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot.catalog.api import ExerciseInfo
from bot.programs.domain import PlanExercise, ProgramPlan
from bot.programs.models import (
    Program,
    ProgramDay,
    ProgramExercise,
    ProgramSession,
    ProgramSet,
)
from bot.workouts.domain import SetEntry


@dataclass(frozen=True)
class StoredExercise:
    exercise_id: int | None  # None — упражнение удалено из каталога
    name: str
    notes: str | None
    # подходы на каждую неделю; пусто — на этой неделе упражнения нет
    weeks: list[list[SetEntry]]


@dataclass(frozen=True)
class StoredDay:
    position: int
    name: str
    exercises: list[StoredExercise]


@dataclass(frozen=True)
class StoredProgram:
    id: int
    weeks: int
    days: list[StoredDay]
    # (неделя, позиция дня) -> пропущена ли; нет ключа — сессия впереди
    done: dict[tuple[int, int], bool]
    imported_at: datetime | None = None


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
                ProgramDay.position,
                ProgramExercise.position,
                ProgramSet.week,
                ProgramSet.position,
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
                    weeks=[[] for _ in range(program.weeks)],
                )
                days[day.id].exercises.append(exercises[ex.id])
            exercises[ex.id].weeks[s.week - 1].append(
                SetEntry(weight=s.weight, reps=s.reps, seconds=s.seconds)
            )
        sessions = await self.session.execute(
            select(
                ProgramSession.week, ProgramSession.day_position, ProgramSession.skipped
            ).where(ProgramSession.program_id == program.id)
        )
        return StoredProgram(
            id=program.id,
            weeks=program.weeks,
            days=list(days.values()),
            done={(week, pos): skipped for week, pos, skipped in sessions.tuples()},
            imported_at=program.imported_at,
        )

    async def replace(
        self, user_id: int, plan: ProgramPlan, exercises: dict[str, ExerciseInfo]
    ) -> None:
        """
        Новая программа вместо старой. exercises — упражнение каталога по
        casefold() названия из плана; название сохраняется каталожное.
        """
        # дни, упражнения, подходы и сессии удаляет каскад внешних ключей
        await self.delete(user_id)
        program = Program(user_id=user_id, weeks=plan.weeks)
        self.session.add(program)
        await self.session.flush()
        # по flush на уровень, а не на строку: id нужны только уровню ниже
        day_rows = [
            ProgramDay(program_id=program.id, position=day_pos, name=day.name)
            for day_pos, day in enumerate(plan.days, start=1)
        ]
        self.session.add_all(day_rows)
        await self.session.flush()
        ex_rows: list[tuple[ProgramExercise, PlanExercise]] = []
        for day_row, day in zip(day_rows, plan.days, strict=True):
            for ex_pos, ex in enumerate(day.exercises, start=1):
                info = exercises[ex.name.casefold()]
                ex_rows.append(
                    (
                        ProgramExercise(
                            day_id=day_row.id,
                            position=ex_pos,
                            exercise_id=info.id,
                            exercise_name=info.name,
                            notes=ex.notes,
                        ),
                        ex,
                    )
                )
        self.session.add_all(row for row, _ in ex_rows)
        await self.session.flush()
        self.session.add_all(
            ProgramSet(
                program_exercise_id=ex_row.id,
                week=week,
                position=set_pos,
                weight=s.weight,
                reps=s.reps,
                seconds=s.seconds,
            )
            for ex_row, ex in ex_rows
            for week, sets in enumerate(ex.weeks, start=1)
            for set_pos, s in enumerate(sets, start=1)
        )
        await self.session.flush()

    async def delete(self, user_id: int) -> bool:
        result = await self.session.execute(
            delete(Program).where(Program.user_id == user_id)
        )
        return result.rowcount > 0

    async def add_session(
        self,
        user_id: int,
        program_id: int,
        week: int,
        day_position: int,
        skipped: bool,
    ) -> bool:
        """
        Сессия сделана или пропущена. False — программу уже заменили или
        удалили. Повтор той же сессии — не ошибка: остаётся первая отметка.
        """
        owned = await self.session.scalar(
            select(Program.id).where(
                Program.id == program_id, Program.user_id == user_id
            )
        )
        if owned is None:
            return False
        await self.session.execute(
            insert(ProgramSession)
            .values(
                program_id=program_id,
                week=week,
                day_position=day_position,
                skipped=skipped,
            )
            .on_conflict_do_nothing(constraint="program_sessions_once")
        )
        return True

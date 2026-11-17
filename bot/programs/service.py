from sqlalchemy.ext.asyncio import AsyncSession

from bot.catalog.api import Catalog, ExerciseInfo
from bot.programs.domain import InvalidProgram, ProgramPlan, sessions
from bot.programs.repository import ProgramRepository, StoredProgram


class ExerciseNotAvailable(InvalidProgram):
    pass


def unmatched_names(plan: ProgramPlan, found: dict[str, ExerciseInfo]) -> list[str]:
    """Названия плана, которых нет в каталоге: каждое один раз, по порядку."""
    seen: set[str] = set()
    names = []
    for day in plan.days:
        for ex in day.exercises:
            key = ex.name.casefold()
            if ex.name not in found and key not in seen:
                seen.add(key)
                names.append(ex.name)
    return names


async def import_program(
    session: AsyncSession,
    user_id: int,
    plan: ProgramPlan,
    exercise_ids: dict[str, int],
) -> None:
    """
    Заменяет программу пользователя. exercise_ids — id упражнения каталога
    по casefold() названия из плана.

    Доступ проверяем здесь, а не в мастере сопоставления: id приходят из
    кнопок, а упражнение могли удалить, пока мастер шёл.
    """
    keys = {ex.name.casefold() for day in plan.days for ex in day.exercises}
    if missing := keys - exercise_ids.keys():
        raise ExerciseNotAvailable(f"exercises not matched: {sorted(missing)}")
    available = await Catalog(session).get_visible_many(
        set(exercise_ids.values()), user_id
    )
    exercises = {}
    for key in keys:
        info = available.get(exercise_ids[key])
        if info is None:
            raise ExerciseNotAvailable(f"exercise not available: {key}")
        exercises[key] = info
    await ProgramRepository(session).replace(user_id, plan, exercises)
    await session.commit()


async def get_program(session: AsyncSession, user_id: int) -> StoredProgram | None:
    return await ProgramRepository(session).get(user_id)


async def delete_program(session: AsyncSession, user_id: int) -> bool:
    deleted = await ProgramRepository(session).delete(user_id)
    if deleted:
        await session.commit()
    return deleted


def next_session(program: StoredProgram) -> tuple[int, int] | None:
    """Первая несделанная сессия (неделя, позиция дня); None — программа пройдена."""
    return next(
        (s for s in sessions(program.days, program.weeks) if s not in program.done),
        None,
    )


def week_sessions(program: StoredProgram, week: int) -> list[tuple[int, int]]:
    """Несделанные сессии недели — дни, которые можно начать."""
    return [
        s
        for s in sessions(program.days, program.weeks)
        if s[0] == week and s not in program.done
    ]


async def complete_session(
    session: AsyncSession,
    user_id: int,
    program_id: int,
    week: int,
    day_position: int,
    skipped: bool = False,
) -> StoredProgram | None:
    """
    Отмечает сессию сделанной или пропущенной и возвращает программу после
    отметки. None — программу заменили или удалили, пока шла тренировка:
    её сессии не трогаем.
    """
    repo = ProgramRepository(session)
    if not await repo.add_session(user_id, program_id, week, day_position, skipped):
        return None
    await session.commit()
    program = await repo.get(user_id)
    if program is None or program.id != program_id:
        # заменили сразу после отметки
        return None
    return program

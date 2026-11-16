from sqlalchemy.ext.asyncio import AsyncSession

from bot.catalog.api import Catalog, ExerciseInfo
from bot.programs.domain import InvalidProgram, ProgramPlan, next_after
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


async def advance(
    session: AsyncSession, user_id: int, program_id: int, done_position: int
) -> None:
    """
    Следующим предложит день после выполненного. Программу могли заменить,
    пока шла тренировка, — тогда её ротацию не трогаем.
    """
    repo = ProgramRepository(session)
    program = await repo.get(user_id)
    if program is None or program.id != program_id:
        return
    position = next_after(done_position, len(program.days))
    if await repo.set_next_position(user_id, program_id, position):
        await session.commit()

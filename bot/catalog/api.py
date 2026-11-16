"""
Всё, что каталог отдаёт другим модулям.

Тренировки и экспорт узнают про упражнения только отсюда, а не из таблиц
каталога
"""

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.catalog.models import Exercise, ExerciseMuscle, Muscle
from bot.catalog.repository import ExerciseRepository

MUSCLES_PROMPT = (
    "Enter muscles separated by comma (e.g. Chest, Tricep):\nor send — to skip"
)


@dataclass(frozen=True)
class ExerciseInfo:
    id: int
    name: str


def parse_muscle_names(text: str) -> list[str]:
    """Ответ на MUSCLES_PROMPT. Пустые части — от лишней запятой — не мышцы."""
    text = text.strip()
    if text in ("—", "-"):
        return []
    return [m.strip() for m in text.split(",") if m.strip()]


def match_names(
    names: list[str], catalog: list[ExerciseInfo]
) -> dict[str, ExerciseInfo]:
    index: dict[str, ExerciseInfo] = {}
    for ex in catalog:
        index.setdefault(ex.name.casefold(), ex)
    return {name: index[name.casefold()] for name in names if name.casefold() in index}


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"\w+", text.casefold()) if len(w) >= 3}


def rank_similar(
    name: str, catalog: list[ExerciseInfo], limit: int = 5
) -> list[ExerciseInfo]:
    """
    По числу общих слов; слово совпадает и по началу — «squats» и «squat».
    Поиск по подстроке тут не помогает: «Barbell Back Squat» не найдёт
    «Back Squat».
    """
    words = _words(name)
    scored = []
    for ex in catalog:
        other = _words(ex.name)
        score = sum(
            any(w.startswith(o) or o.startswith(w) for o in other) for w in words
        )
        if score:
            # при равном счёте выше то, где меньше лишних слов
            scored.append((-score, len(other) - score, ex.name, ex))
    scored.sort(key=lambda item: item[:3])
    return [ex for *_, ex in scored[:limit]]


class Catalog:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def search(
        self, query: str, user_id: int, limit: int = 20
    ) -> tuple[list[ExerciseInfo], int]:
        exercises, total = await ExerciseRepository(self.session).search_by_name(
            query, user_id, limit
        )
        return [ExerciseInfo(id=ex.id, name=ex.name) for ex in exercises], total

    async def get_visible(self, exercise_id: int, user_id: int) -> ExerciseInfo | None:
        """Упражнение, если пользователь может им пользоваться: своё или общее."""
        ex = await ExerciseRepository(self.session).get_visible(exercise_id, user_id)
        return ExerciseInfo(id=ex.id, name=ex.name) if ex else None

    async def get_visible_many(
        self, exercise_ids: set[int], user_id: int
    ) -> dict[int, ExerciseInfo]:
        """Те из exercise_ids, что доступны пользователю."""
        if not exercise_ids:
            return {}
        result = await self.session.execute(
            select(Exercise.id, Exercise.name).where(
                Exercise.id.in_(exercise_ids), Exercise.visible_to(user_id)
            )
        )
        return {
            ex_id: ExerciseInfo(id=ex_id, name=name)
            for ex_id, name in result.tuples().all()
        }

    async def by_names(self, names: list[str], user_id: int) -> dict[str, ExerciseInfo]:
        """
        Доступные пользователю упражнения с этими названиями, без учёта
        регистра; ключи — названия как во входе.
        """
        return match_names(names, await self.visible(user_id))

    async def similar(
        self, name: str, user_id: int, limit: int = 5
    ) -> list[ExerciseInfo]:
        """Упражнения с общими словами в названии — самые похожие первыми."""
        return rank_similar(name, await self.visible(user_id), limit)

    async def visible(self, user_id: int) -> list[ExerciseInfo]:
        """
        Весь доступный пользователю каталог. Названия сравниваем в Python:
        lower() в Postgres зависит от локали базы и кириллицу может не
        опустить. Каталог — сотни строк, не больше.
        """
        result = await self.session.execute(
            select(Exercise.id, Exercise.name)
            .where(Exercise.visible_to(user_id))
            .order_by(Exercise.id)
        )
        return [ExerciseInfo(id=i, name=n) for i, n in result.tuples().all()]

    async def muscles(self, exercise_ids: set[int]) -> dict[int, list[str]]:
        """
        Мышцы упражнений по алфавиту.

        Доступ здесь не проверяется: ids приходят из тренировок самого
        пользователя. Удалённых упражнений в ответе нет — их мышцы удалены
        вместе с ними.
        """
        if not exercise_ids:
            return {}
        result = await self.session.execute(
            select(ExerciseMuscle.exercise_id, Muscle.name)
            .join(Muscle, Muscle.id == ExerciseMuscle.muscle_id)
            .where(ExerciseMuscle.exercise_id.in_(exercise_ids))
            .order_by(Muscle.name)
        )
        muscles: dict[int, list[str]] = {}
        for exercise_id, name in result.tuples().all():
            muscles.setdefault(exercise_id, []).append(name)
        return muscles

"""
Черновик тренировки в FSM и его превращение в WorkoutRecord.

  exercises: [{"exercise_id": int, "exercise_name": str, "notes": str | None,
               "sets": [{"weight": Decimal | None, "reps": int | None,
                         "seconds": int | None}]}]
  started_at, finished_at: str — /workout и последнее Finish session, ISO в UTC

Тренировка по дню программы — ещё:

  program_id: int, program_day: str, program_day_position: int,
  program_week: int
  plan: [{"exercise_id": int | None, "name": str, "notes": str | None,
          "deleted": bool, "sets": [set]}] — план дня, копия: программу
          могут заменить, пока идёт тренировка
  exercises[].plan_index: int — пункт плана, по которому сделано упражнение
  current_plan_index, current_plan_sets, current_plan_hint — то же для
          упражнения, которое вводят сейчас; current_sets[].plan_idx —
          плановый подход, отмеченный галочкой

Ключи seconds, notes, started_at и finished_at появились позже: в черновиках,
начатых раньше, их нет, и такие черновики должны сохраняться так же.
"""

from datetime import UTC, date, datetime, time, timedelta
from typing import TYPE_CHECKING, Any

from bot.users.settings import to_local
from bot.workouts.domain import (
    MAX_WORKOUT_DURATION,
    ExerciseEntry,
    SetEntry,
    WorkoutRecord,
)

if TYPE_CHECKING:
    from bot.programs.repository import StoredProgram


def utc_now_iso() -> str:
    """Момент для черновика — строкой: fsm_json не умеет datetime."""
    return datetime.now(UTC).isoformat()


def set_to_fsm(entry: SetEntry) -> dict[str, Any]:
    return {"weight": entry.weight, "reps": entry.reps, "seconds": entry.seconds}


def sets_from_fsm(sets: list[dict[str, Any]]) -> list[SetEntry]:
    return [
        SetEntry(weight=s["weight"], reps=s["reps"], seconds=s.get("seconds"))
        for s in sets
    ]


def seed_plan(
    data: dict[str, Any], program: "StoredProgram", week: int, position: int
) -> None:
    """
    Кладёт в черновик план дня position на неделе week. Упражнения, которых
    на этой неделе нет, в план не попадают.
    """
    day = next(d for d in program.days if d.position == position)
    data.update(
        program_id=program.id,
        program_day=day.name,
        program_day_position=position,
        program_week=week,
        plan=[
            {
                "exercise_id": ex.exercise_id,
                "name": ex.name,
                "notes": ex.notes,
                # удалённое из каталога в тренировку не добавить
                "deleted": ex.exercise_id is None,
                "sets": [set_to_fsm(s) for s in ex.weeks[week - 1]],
            }
            for ex in day.exercises
            if ex.weeks[week - 1]
        ],
    )


def plan_statuses(data: dict[str, Any]) -> list[tuple[str, str]] | None:
    """(название, done | todo | deleted) по пунктам плана; None — плана нет."""
    if "plan" not in data:
        return None
    done = {ex.get("plan_index") for ex in data.get("exercises", [])}
    return [
        (
            item["name"],
            "deleted" if item["deleted"] else "done" if i in done else "todo",
        )
        for i, item in enumerate(data["plan"])
    ]


def plan_todo(data: dict[str, Any]) -> list[tuple[int, str]]:
    """Пункты плана, которые ещё можно сделать: (номер, название)."""
    return [
        (i, name)
        for i, (name, status) in enumerate(plan_statuses(data) or [])
        if status == "todo"
    ]


def toggle_plan_set(
    current_sets: list[dict[str, Any]], plan_sets: list[dict[str, Any]], idx: int
) -> None:
    """Галочка у планового подхода idx: ставит его в конец или снимает."""
    for i, s in enumerate(current_sets):
        if s.get("plan_idx") == idx:
            del current_sets[i]
            return
    current_sets.append({**plan_sets[idx], "plan_idx": idx})


def workout_times(data: dict[str, Any], utc_offset: int) -> tuple[time, time] | None:
    """
    Начало и конец по часам пользователя. None — время не записываем:
    черновик начат до обновления, тренировку забыли закончить или дату
    ввели вручную.
    """
    if "started_at" not in data or "finished_at" not in data:
        return None
    started = datetime.fromisoformat(data["started_at"])
    finished = datetime.fromisoformat(data["finished_at"])
    if not timedelta(0) <= finished - started <= MAX_WORKOUT_DURATION:
        return None
    start = to_local(started, utc_offset).replace(second=0, microsecond=0)
    end = to_local(finished, utc_offset).replace(second=0, microsecond=0)
    if date.fromisoformat(data["workout_date"]) not in (start.date(), end.date()):
        return None
    return start.time(), end.time()


def build_record(user_id: int, data: dict[str, Any], utc_offset: int) -> WorkoutRecord:
    """Собирает тренировку через доменные конструкторы — с их проверками."""
    exercises = [
        ExerciseEntry.create(
            ex["exercise_id"],
            [
                SetEntry.create(s["weight"], s["reps"], s.get("seconds"))
                for s in ex["sets"]
            ],
            ex.get("notes"),
        )
        for ex in data.get("exercises", [])
    ]
    start_time, end_time = workout_times(data, utc_offset) or (None, None)
    return WorkoutRecord.create(
        user_id=user_id,
        workout_date=date.fromisoformat(data["workout_date"]),
        notes=data.get("notes"),
        exercises=exercises,
        start_time=start_time,
        end_time=end_time,
    )


def minutes_since_start(data: dict[str, Any], now: datetime) -> int | None:
    if "started_at" not in data:
        return None
    elapsed = now - datetime.fromisoformat(data["started_at"])
    return max(0, int(elapsed.total_seconds() // 60))


def workout_today(data: dict[str, Any], utc_offset: int, now: datetime) -> date:
    """
    «Сегодня» для тренировки — день нажатия Finish session по часам
    пользователя: Today или Yes могут нажать уже после полуночи.
    """
    finished_at = data.get("finished_at")
    moment = datetime.fromisoformat(finished_at) if finished_at else now
    return to_local(moment, utc_offset).date()

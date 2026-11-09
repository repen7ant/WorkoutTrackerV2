"""
Черновик тренировки в FSM и его превращение в WorkoutRecord.

  exercises: [{"exercise_id": int, "exercise_name": str, "notes": str | None,
               "sets": [{"weight": Decimal | None, "reps": int | None,
                         "seconds": int | None}]}]
  started_at, finished_at: str — /workout и последнее Finish session, ISO в UTC

Ключи seconds, notes, started_at и finished_at появились позже: в черновиках,
начатых раньше, их нет, и такие черновики должны сохраняться так же.
"""

from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from bot.users.settings import to_local
from bot.workouts.domain import ExerciseEntry, SetEntry, WorkoutRecord

# дольше — скорее всего, тренировку забыли закончить
MAX_WORKOUT_DURATION = timedelta(hours=6)


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

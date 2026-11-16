"""
План в FSM, пока идёт мастер импорта, и текст из .txt-файла.

  plan: {"days": [{"name": str, "exercises": [{"name": str,
         "notes": str | None, "weeks": [[set_to_fsm]]}]}]}
"""

from typing import Any

from bot.programs.domain import InvalidProgram, PlanDay, PlanExercise, ProgramPlan
from bot.workouts.draft import set_to_fsm, sets_from_fsm


def plan_to_fsm(plan: ProgramPlan) -> dict[str, Any]:
    return {
        "days": [
            {
                "name": day.name,
                "exercises": [
                    {
                        "name": ex.name,
                        "notes": ex.notes,
                        "weeks": [[set_to_fsm(s) for s in week] for week in ex.weeks],
                    }
                    for ex in day.exercises
                ],
            }
            for day in plan.days
        ]
    }


def plan_from_fsm(data: dict[str, Any]) -> ProgramPlan:
    return ProgramPlan.create(
        [
            PlanDay.create(
                day["name"],
                [
                    PlanExercise.create(
                        ex["name"],
                        [sets_from_fsm(week) for week in ex["weeks"]],
                        ex["notes"],
                    )
                    for ex in day["exercises"]
                ],
            )
            for day in data["days"]
        ]
    )


def decode_txt(raw: bytes) -> str:
    try:
        # utf-8-sig: Блокнот Windows ставит BOM в начало файла
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise InvalidProgram("file must be UTF-8 text") from None

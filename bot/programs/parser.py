"""
Текст программы от ИИ → ProgramPlan.

Ошибка в любой строке отклоняет весь импорт: с номером строки и причиной,
чтобы текст можно было поправить и прислать снова.
"""

import re

from bot.programs.domain import (
    MAX_DAY_EXERCISES,
    MAX_DAY_NAME,
    MAX_DAYS,
    MAX_EXERCISE_SETS,
    InvalidProgram,
    PlanDay,
    PlanExercise,
    ProgramPlan,
)
from bot.workouts.domain import MAX_EXERCISE_NOTES, SetEntry
from bot.workouts.set_parse import parse_set

PROGRAM_MARKER = "# PROGRAM"

FORMAT_DESCRIPTION = f"""\
```
{PROGRAM_MARKER}
== Day name ==
Exercise name: 100x5, 100x5, 100x5 | notes: rest 3 min
Exercise name: BWx12, BWx12, BWx12
Exercise name: BWx1:30, BWx1:30
```

- The block starts with the line `{PROGRAM_MARKER}`.
- `== Day name ==` starts a training day. Days are trained in rotation, in the
  order listed: {MAX_DAYS} days at most, unique names of up to {MAX_DAY_NAME}
  characters.
- One line per exercise: the name, a colon, then every set as weight x reps,
  separated by commas, in the order they are performed: up to
  {MAX_DAY_EXERCISES} exercises per day and {MAX_EXERCISE_SETS} sets per exercise.
- Weight is in kilograms; `BW` means bodyweight only. A time in place of reps
  (`1:30`, minutes:seconds) makes a timed set.
- Exact numbers only: one fixed weight and rep count per set. No rep ranges
  (8-12), no RPE or percentages, no weeks or progression schemes.
- `| notes:` is optional: a rest time or technique cue on the same line, up to
  {MAX_EXERCISE_NOTES} characters. A variation (paused, incline) is a separate
  exercise with its own name, not a note.
- Nothing else inside the block: no comments, no markdown, no explanations."""

_DAY = re.compile(r"==+(.*?)==+")
# подход и запятая после него; делить строку по запятым нельзя — вес бывает
# с запятой: «102,5x5»
_SET = re.compile(
    r"\s*((?:BW|\d+(?:[.,]\d+)?)\s*[XХ]\s*(?:\d+:\d\d|\d+[SС]?))\s*(?:,|$)",
    re.IGNORECASE,
)
_NOTES = re.compile(r"\s*notes:(.*)", re.IGNORECASE)
# двоеточие перед подходами: в «1:30» за ним цифра, а не пробел
_NAME_COLON = re.compile(r":(?=\s)")


class ProgramParseError(InvalidProgram):
    def __init__(self, line: int, reason: str):
        super().__init__(f"line {line}: {reason}")
        self.line = line
        self.reason = reason


def _parse_sets(text: str) -> list[SetEntry]:
    sets = []
    pos = 0
    while text[pos:].strip():
        m = _SET.match(text, pos)
        if m is None:
            piece = text[pos:].split(",")[0].strip()
            raise InvalidProgram(f'can\'t parse set "{piece}"')
        token = re.sub(r"\s+", "", m[1])
        entry = parse_set(token)
        if entry is None:
            raise InvalidProgram(f'invalid set "{token}"')
        sets.append(entry)
        pos = m.end()
    return sets


def _parse_exercise(line: str) -> PlanExercise:
    main, bar, rest = line.partition("|")
    notes = None
    if bar:
        m = _NOTES.fullmatch(rest)
        if m is None:
            raise InvalidProgram('expected "| notes: ..." after the sets')
        notes = m[1]
    # название само может быть с двоеточием: «Row: chest supported: 40x10»
    colons = [m.start() for m in _NAME_COLON.finditer(main)]
    split = colons[-1] if colons else main.find(":")
    if split < 0:
        raise InvalidProgram(f'expected "Exercise: sets", got "{line}"')
    return PlanExercise.create(main[:split], _parse_sets(main[split + 1 :]), notes)


def _add_day(
    days: list[PlanDay], line: int, name: str, exercises: list[PlanExercise]
) -> None:
    """Ошибки дня — и лишний день, и повтор имени — на строке его заголовка."""
    try:
        days.append(PlanDay.create(name, exercises))
        ProgramPlan.create(days)
    except InvalidProgram as e:
        raise ProgramParseError(line, str(e)) from None


def parse_program(text: str) -> ProgramPlan:
    numbered = [
        (number, line.strip())
        for number, line in enumerate(text.splitlines(), start=1)
        if line.strip()
    ]
    if not numbered or numbered[0][1] != PROGRAM_MARKER:
        raise ProgramParseError(
            numbered[0][0] if numbered else 1,
            f'first line must be "{PROGRAM_MARKER}"',
        )

    days: list[PlanDay] = []
    day_line, day_name = 0, None
    exercises: list[PlanExercise] = []
    for number, line in numbered[1:]:
        if m := _DAY.fullmatch(line):
            if day_name is not None:
                _add_day(days, day_line, day_name, exercises)
            day_line, day_name, exercises = number, m[1], []
            continue
        if day_name is None:
            raise ProgramParseError(number, "exercise before the first day")
        try:
            exercises.append(_parse_exercise(line))
        except InvalidProgram as e:
            raise ProgramParseError(number, str(e)) from None
    if day_name is not None:
        _add_day(days, day_line, day_name, exercises)

    try:
        return ProgramPlan.create(days)
    except InvalidProgram as e:
        raise ProgramParseError(numbered[0][0], str(e)) from None

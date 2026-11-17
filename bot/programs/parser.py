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
    MAX_WEEKS,
    InvalidProgram,
    PlanDay,
    PlanExercise,
    ProgramPlan,
    different_weeks,
)
from bot.workouts.domain import MAX_EXERCISE_NOTES, SetEntry
from bot.workouts.set_parse import parse_set

PROGRAM_MARKER = "# PROGRAM"

FORMAT_DESCRIPTION = f"""\
```
{PROGRAM_MARKER}
== Day name ==
Exercise name: 100x5x3 / 102.5x5x3 / 105x5x3 / 90x5x2 | notes: rest 3 min
Exercise name: BWx10x3 / BWx12x3 / BWx12x4 / -
Exercise name: BWx1:00, BWx1:30 / BWx1:30x2 / BWx1:45x2 / BWx1:00
```

- The block starts with the line `{PROGRAM_MARKER}`.
- The program is a cycle of 1-{MAX_WEEKS} weeks with the same training days every
  week. Give a progression across the weeks and a deload where it makes sense.
- `== Day name ==` starts a training day: {MAX_DAYS} days at most, unique names of
  up to {MAX_DAY_NAME} characters. Days of a week can be trained in any order.
- One line per exercise: the name, a colon, then the sets for each week,
  separated by ` / `. Every exercise lists the same number of weeks: that is
  the length of the program. `-` means the exercise is not done that week.
- Sets of a week are separated by commas, in the order they are performed:
  weight x reps, and `x3` at the end for 3 identical sets (`100x5x3`). Up to
  {MAX_DAY_EXERCISES} exercises per day and {MAX_EXERCISE_SETS} sets per exercise
  per week.
- Weight is in kilograms; `BW` means bodyweight only. A time in place of reps
  (`1:30`, minutes:seconds) makes a timed set.
- Exact numbers only: one fixed weight and rep count per set. No rep ranges
  (8-12), no RPE or percentages.
- `| notes:` is optional: a rest time or technique cue on the same line, up to
  {MAX_EXERCISE_NOTES} characters. A variation (paused, incline) is a separate
  exercise with its own name, not a note.
- Nothing else inside the block: no comments, no markdown, no explanations."""

# ИИ отдаёт блок в ```-рамке, и её могут скопировать вместе с ним
_FENCE = re.compile(r"```[\w-]*")
# «# Program», «#PROGRAM» — тоже маркер
_MARKER = re.compile(r"#\s*program", re.IGNORECASE)
_DAY = re.compile(r"==+(.*?)==+")
# подход и запятая после него; делить строку по запятым нельзя — вес бывает
# с запятой: «102,5x5»
# «x3» в конце — три одинаковых подхода
_SET = re.compile(
    r"\s*(?P<set>(?:BW|\d+(?:[.,]\d+)?)\s*[XХ]\s*(?:\d+:\d\d|\d+[SС]?))"
    r"(?:\s*[XХ]\s*(?P<count>\d+))?\s*(?:,|$)",
    re.IGNORECASE,
)
# по «| notes:», а не первому «|»: название из каталога бывает с «|»
_NOTES = re.compile(r"\|\s*notes:(.*)", re.IGNORECASE)
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
        token = re.sub(r"\s+", "", m["set"])
        entry = parse_set(token)
        if entry is None:
            raise InvalidProgram(f'invalid set "{token}"')
        count = int(m["count"]) if m["count"] else 1
        if not 1 <= count <= MAX_EXERCISE_SETS:
            whole = re.sub(r"\s+", "", m[0]).rstrip(",")
            raise InvalidProgram(f'invalid set count "{whole}"')
        sets.extend([entry] * count)
        pos = m.end()
    return sets


def _parse_weeks(text: str) -> list[list[SetEntry]]:
    weeks = []
    for n, week in enumerate(text.split("/"), start=1):
        week = week.strip()
        if week == "-":
            weeks.append([])
        elif not week:
            raise InvalidProgram(f'week {n} has no sets (use "-" to skip a week)')
        else:
            weeks.append(_parse_sets(week))
    return weeks


def _parse_exercise(line: str) -> PlanExercise:
    m = _NOTES.search(line)
    main = line[: m.start()] if m else line
    notes = m[1] if m else None
    # название само может быть с двоеточием: «Row: chest supported: 40x10»
    colons = [c.start() for c in _NAME_COLON.finditer(main)]
    split = colons[-1] if colons else main.find(":")
    if split < 0:
        raise InvalidProgram(f'expected "Exercise: sets", got "{line}"')
    if "|" in main[split + 1 :]:
        raise InvalidProgram('expected "| notes: ..." after the sets')
    return PlanExercise.create(main[:split], _parse_weeks(main[split + 1 :]), notes)


def _add_day(
    days: list[PlanDay], line: int, name: str, exercises: list[PlanExercise]
) -> None:
    """Ошибки дня — и лишний день, и повтор имени — на строке его заголовка."""
    try:
        days.append(PlanDay.create(name, exercises))
        ProgramPlan.create(days)
    except InvalidProgram as e:
        raise ProgramParseError(line, str(e)) from None


def _content_lines(text: str) -> list[tuple[int, str]]:
    """Непустые строки без рамок ```, с номерами строк исходного текста."""
    return [
        (number, line.strip())
        for number, line in enumerate(text.splitlines(), start=1)
        if line.strip() and not _FENCE.fullmatch(line.strip())
    ]


def has_program_marker(text: str) -> bool:
    lines = _content_lines(text)
    return bool(lines) and _MARKER.fullmatch(lines[0][1]) is not None


def parse_program(text: str) -> ProgramPlan:
    numbered = _content_lines(text)
    if not numbered or not _MARKER.fullmatch(numbered[0][1]):
        raise ProgramParseError(
            numbered[0][0] if numbered else 1,
            f'first line must be "{PROGRAM_MARKER}"',
        )

    days: list[PlanDay] = []
    day_line, day_name = 0, None
    exercises: list[PlanExercise] = []
    # длина программы — по первому упражнению
    weeks: int | None = None
    for number, line in numbered[1:]:
        if m := _DAY.fullmatch(line):
            if day_name is not None:
                _add_day(days, day_line, day_name, exercises)
            day_line, day_name, exercises = number, m[1], []
            continue
        if day_name is None:
            raise ProgramParseError(number, "exercise before the first day")
        try:
            exercise = _parse_exercise(line)
        except InvalidProgram as e:
            raise ProgramParseError(number, str(e)) from None
        if weeks is None:
            weeks = len(exercise.weeks)
        elif len(exercise.weeks) != weeks:
            raise ProgramParseError(
                number, different_weeks(exercise.name, len(exercise.weeks), weeks)
            )
        exercises.append(exercise)
    if day_name is not None:
        _add_day(days, day_line, day_name, exercises)

    try:
        return ProgramPlan.create(days)
    except InvalidProgram as e:
        raise ProgramParseError(numbered[0][0], str(e)) from None

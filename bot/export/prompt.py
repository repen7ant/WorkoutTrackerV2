from datetime import date

from bot.common.formatting import format_set_compact
from bot.export.service import ExportWorkout
from bot.programs.parser import FORMAT_DESCRIPTION, PROGRAM_MARKER
from bot.workouts.domain import duration_minutes


def _one_line(text: str) -> str:
    # в заметке из Telegram бывают переводы строк, а в логе запись — одна строка
    return " ".join(text.split())


TASK_INTRO = """\
## TASK
Cover every point below. Lean on the actual numbers in the log: cite specific
dates, weights and rep counts instead of giving generic advice."""

ANALYSIS_ITEMS = """\
1. Progress per exercise
   For each exercise, compare the start of the period with the end: how working
   weights, reps and set counts changed, in kilograms and in percent. State
   plainly which lifts went up, which stalled and which went down.

2. Volume and intensity
   Tonnage (weight x reps, summed) per exercise and per muscle group, and how it
   moved over the period. Estimate 1RM (Epley or similar) for the main lifts so
   strength can be compared across different set and rep schemes. Point out where
   volume grew without strength following, or the other way round.

3. Patterns and consistency
   Training frequency, gaps and streaks, how often each exercise was trained,
   which exercises were dropped or picked up. Connect the athlete's notes
   (fatigue, pain, good and bad days) to the numbers around them. Flag plateaus
   and anything that looks like accumulated fatigue or overreaching.

4. Balance
   How the work is spread across muscle groups: push versus pull, upper versus
   lower, and any group clearly under- or over-trained relative to the rest."""

PLAN_VERSUS_ACTUAL = """\
5. Plan versus actual
   Compare each workout with the program day it followed (`day:`). Where does the
   athlete consistently do more or less than planned: sets, reps, weight? Which
   planned exercises get skipped and which are added on top? Judge from this
   whether the current program fits the athlete."""

RESTRUCTURING = """\
{n}. Program restructuring
   Building on everything above, propose how to restructure the training program:
   what to keep, what to cut, what to add, how to spread frequency and volume
   across the week, and where to push weight versus reps. Give concrete numbers
   (sets, reps, weights) for the next training cycle."""

OUTPUT = f"""\
## OUTPUT
- Open with a short summary: the 3-5 most important findings.
- Then one section per task item above.
- Use tables where numbers are easier to compare that way.
- Be direct about weak spots; do not soften the assessment.
- Where the data is too sparse to support a conclusion, say so instead of guessing.
- End the answer with the new program as a single `{PROGRAM_MARKER}` block in a code
  block, and write nothing after it. The athlete pastes this block into a tracker
  app that reads it line by line, so follow the format below exactly.
- Pick exercises from EXERCISES, AVAILABLE EXERCISES and CURRENT PROGRAM, with
  names written exactly as there. A new name only when none of them fits. A
  variation (paused, incline, close-grip) is a separate exercise with its own
  name; notes are for rest times and technique cues only.

Program format:

{FORMAT_DESCRIPTION}"""


def _exercise_lines(exercises: dict[str, list[str]]) -> list[str]:
    return [
        f"{name} — {', '.join(muscles) if muscles else 'muscle groups not set'}"
        for name, muscles in sorted(exercises.items())
    ]


def _task(with_plan: bool) -> str:
    items = [ANALYSIS_ITEMS]
    if with_plan:
        items.append(PLAN_VERSUS_ACTUAL)
    items.append(RESTRUCTURING.format(n=6 if with_plan else 5))
    return f"{TASK_INTRO}\n\n" + "\n\n".join(items)


def build_ai_prompt(
    workouts: list[ExportWorkout],
    period_label: str,
    date_from: date | None,
    date_to: date,
    wishes: str | None = None,
    program_text: str | None = None,
    available: dict[str, list[str]] | None = None,
) -> str:
    """available — весь каталог пользователя: название -> мышцы."""
    range_from = date_from or workouts[0]["date"]
    total_sets = sum(
        len(ex["sets"]) for workout in workouts for ex in workout["exercises"]
    )
    # день плана бывает и без текущей программы: её могли удалить
    has_days = any(workout.get("program_day") for workout in workouts)

    legend: dict[str, list[str]] = {}
    for workout in workouts:
        for ex in workout["exercises"]:
            legend.setdefault(ex["name"], ex["muscles"])

    lines = [
        "# WORKOUT LOG — AI ANALYSIS REQUEST",
        "",
        "You are an experienced strength coach. Analyse the training log below,",
        "write a report on this athlete's progress and design their next program.",
        "",
        "## CONTEXT",
        f"Period: {period_label} ({range_from.isoformat()} … {date_to.isoformat()})",
        (
            f"Workouts: {len(workouts)} | Exercises used: {len(legend)} | "
            f"Sets logged: {total_sets}"
        ),
        "Data format:",
        "- Each block starts with a workout date (YYYY-MM-DD), then, if recorded,",
        "  start–end time and duration in minutes. A `notes:` part is the athlete's",
        "  own comment on that workout.",
    ]
    if has_days:
        lines += [
            "- A `day:` part names the program day the workout followed"
            + (" (see CURRENT PROGRAM)." if program_text else "."),
        ]
    lines += [
        "- Below it, one line per exercise. `Bench Press: 100x5, 100x5, 102.5x4`",
        "  means weight in kilograms x repetitions, sets listed in the order they",
        "  were performed.",
        "- A `notes:` part after an exercise's sets is the athlete's comment on that",
        "  exercise.",
        "- `BW` in place of a weight means bodyweight only, no external load.",
        "- A time in place of reps (`BWx1:30`, minutes:seconds) marks a timed set:",
        "  the load was held or carried that long. Leave timed sets out of tonnage",
        "  and compare them by time and weight.",
        "- Exercises are listed in the order they were performed. The muscle groups",
        "  each one trains are listed in the EXERCISES section below.",
        "- Workouts are ordered oldest first, newest last.",
        "",
        "## EXERCISES",
    ]

    lines += _exercise_lines(legend)

    logged = {name.casefold() for name in legend}
    others = {
        name: muscles
        for name, muscles in (available or {}).items()
        if name.casefold() not in logged
    }
    if others:
        lines += [
            "",
            "## AVAILABLE EXERCISES",
            "Other exercises in the athlete's catalog, not in this log yet:",
            *_exercise_lines(others),
        ]

    if program_text:
        lines += [
            "",
            "## CURRENT PROGRAM",
            "The program the athlete follows now. Its days are trained in rotation.",
            "",
            "```",
            program_text,
            "```",
        ]

    lines.extend(["", "## DATA"])
    for workout in workouts:
        header = workout["date"].isoformat()
        start, end = workout["start_time"], workout["end_time"]
        if start is not None and end is not None:
            header += f" {start:%H:%M}–{end:%H:%M} ({duration_minutes(start, end)} min)"
        if workout.get("program_day"):
            header += f" | day: {workout['program_day']}"
        if workout["notes"]:
            header += f" | notes: {_one_line(workout['notes'])}"
        lines.append(header)
        for ex in workout["exercises"]:
            sets_str = ", ".join(format_set_compact(s) for s in ex["sets"])
            line = f"  {ex['name']}: {sets_str}"
            if ex["notes"]:
                line += f" | notes: {_one_line(ex['notes'])}"
            lines.append(line)
        lines.append("")

    if wishes:
        lines += [
            "## ATHLETE REQUESTS",
            "The athlete's own preferences and limits. Take them into account in the",
            "analysis and follow them strictly in the new program; where they conflict",
            "with the log, they win.",
            "",
            wishes,
            "",
        ]

    lines += [_task(with_plan=program_text is not None), "", OUTPUT]
    return "\n".join(lines)

from datetime import date
from decimal import Decimal

from bot.export.service import ExportWorkout


def _format_weight_compact(weight: Decimal | None) -> str:
    if weight is None:
        return "BW"
    return f"{weight.normalize():f}"


AI_TASK = """## TASK
Cover every point below. Lean on the actual numbers in the log: cite specific
dates, weights and rep counts instead of giving generic advice.

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
   lower, and any group clearly under- or over-trained relative to the rest.

5. Program restructuring
   Building on everything above, propose how to restructure the training program:
   what to keep, what to cut, what to add, how to spread frequency and volume
   across the week, and where to push weight versus reps. Give concrete numbers
   (sets, reps, weights) for the next training cycle.

## OUTPUT
- Open with a short summary: the 3-5 most important findings.
- Then one section per task item above.
- Use tables where numbers are easier to compare that way.
- Be direct about weak spots; do not soften the assessment.
- Where the data is too sparse to support a conclusion, say so instead of guessing."""


def build_ai_prompt(
    workouts: list[ExportWorkout],
    period_label: str,
    date_from: date | None,
    date_to: date,
) -> str:
    range_from = date_from or workouts[0]["date"]
    total_sets = sum(
        len(ex["sets"]) for workout in workouts for ex in workout["exercises"]
    )

    legend: dict[str, list[str]] = {}
    for workout in workouts:
        for ex in workout["exercises"]:
            legend.setdefault(ex["name"], ex["muscles"])

    lines = [
        "# WORKOUT LOG — AI ANALYSIS REQUEST",
        "",
        "You are an experienced strength coach. Analyse the training log below",
        "and write a report on this athlete's progress.",
        "",
        "## CONTEXT",
        f"Period: {period_label} ({range_from.isoformat()} … {date_to.isoformat()})",
        (
            f"Workouts: {len(workouts)} | Exercises used: {len(legend)} | "
            f"Sets logged: {total_sets}"
        ),
        "Data format:",
        "- Each block starts with a workout date (YYYY-MM-DD). A `notes:` part is",
        "  the athlete's own comment on that workout.",
        "- Below it, one line per exercise. `Bench Press: 100x5, 100x5, 102.5x4`",
        "  means weight in kilograms x repetitions, sets listed in the order they",
        "  were performed.",
        "- `BW` in place of a weight means bodyweight only, no external load.",
        "- Exercises are listed in the order they were performed. The muscle groups",
        "  each one trains are listed in the EXERCISES section below.",
        "- Workouts are ordered oldest first, newest last.",
        "",
        "## EXERCISES",
    ]

    for name in sorted(legend):
        muscles = ", ".join(legend[name]) if legend[name] else "muscle groups not set"
        lines.append(f"{name} — {muscles}")

    lines.extend(["", "## DATA"])
    for workout in workouts:
        header = workout["date"].isoformat()
        if workout["notes"]:
            header += f" | notes: {workout['notes']}"
        lines.append(header)
        for ex in workout["exercises"]:
            sets_str = ", ".join(
                f"{_format_weight_compact(s['weight'])}x{s['reps']}" for s in ex["sets"]
            )
            lines.append(f"  {ex['name']}: {sets_str}")
        lines.append("")

    lines.append(AI_TASK)
    return "\n".join(lines)

import asyncio
from decimal import Decimal
from types import SimpleNamespace

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from bot.catalog.api import ExerciseInfo
from bot.programs.repository import StoredDay, StoredExercise, StoredProgram
from bot.users.models import User
from bot.utils import fsm_json
from bot.workouts.domain import SetEntry
from bot.workouts.draft import plan_statuses, plan_todo, seed_plan, toggle_plan_set
from bot.workouts.formatters import format_current_sets, format_workout_main
from bot.workouts.handlers import recording
from bot.workouts.handlers.common import LAST_WEEK, PROGRAM_FINISHED, workout_main_view
from bot.workouts.keyboards import (
    WkDay,
    WkPlanEx,
    WkPlanSet,
    WkSkip,
    day_choice_kb,
    set_entered_kb,
    workout_main_kb,
)
from bot.workouts.states import WorkoutSession

BENCH_SETS = [SetEntry(Decimal("100.00"), 5), SetEntry(Decimal("100.00"), 5)]
BENCH_WEEK2 = [SetEntry(Decimal("102.50"), 5)] * 3


def _program(done=None) -> StoredProgram:
    """2 недели; второй жим в Push — только на первой."""
    return StoredProgram(
        id=7,
        weeks=2,
        days=[
            StoredDay(
                1,
                "Push",
                [
                    StoredExercise(
                        1, "Bench Press", "pause", [BENCH_SETS, BENCH_WEEK2]
                    ),
                    StoredExercise(None, "Old Fly", None, [[SetEntry(None, 12)]] * 2),
                    StoredExercise(
                        1, "Bench Press", None, [[SetEntry(Decimal("80"), 10)], []]
                    ),
                ],
            ),
            StoredDay(
                2, "Pull", [StoredExercise(5, "Row", None, [[SetEntry(None, 8)]] * 2)]
            ),
            StoredDay(
                3, "Legs", [StoredExercise(6, "Squat", None, [[SetEntry(None, 5)]] * 2)]
            ),
        ],
        done=done or {},
    )


PROGRAM = _program()
USER = User(id=42)


def rows(kb):
    return [[(b.text, b.callback_data) for b in row] for row in kb.inline_keyboard]


def _seeded(week=1, position=1) -> dict:
    data = {"exercises": []}
    seed_plan(data, PROGRAM, week, position)
    return fsm_json.loads(fsm_json.dumps(data))


def test_day_choice_kb_order():
    days = [(d.position, d.name) for d in PROGRAM.days]
    assert rows(day_choice_kb(7, 1, days, next_position=2)) == [
        [("▶ Start Pull", WkDay(program_id=7, week=1, position=2).pack())],
        [
            ("Push", WkDay(program_id=7, week=1, position=1).pack()),
            ("Legs", WkDay(program_id=7, week=1, position=3).pack()),
        ],
        [
            ("Skip Pull", WkSkip(program_id=7, week=1, position=2).pack()),
            ("Free workout", "wk_free"),
        ],
    ]


def test_day_choice_kb_stale_next_position():
    days = [(d.position, d.name) for d in PROGRAM.days]
    assert rows(day_choice_kb(7, 2, days, next_position=9))[0] == [
        ("▶ Start Push", WkDay(program_id=7, week=2, position=1).pack())
    ]


def test_seed_plan_marks_deleted():
    data = _seeded()
    assert (
        data["program_id"],
        data["program_day"],
        data["program_day_position"],
        data["program_week"],
    ) == (7, "Push", 1, 1)
    assert [(p["name"], p["deleted"]) for p in data["plan"]] == [
        ("Bench Press", False),
        ("Old Fly", True),
        ("Bench Press", False),
    ]
    assert data["plan"][0]["sets"][0] == {
        "weight": Decimal("100.00"),
        "reps": 5,
        "seconds": None,
    }
    assert plan_todo(data) == [(0, "Bench Press"), (2, "Bench Press")]


def test_seed_plan_takes_week_sets():
    data = _seeded(week=2)
    assert data["program_week"] == 2
    # второго жима на неделе 2 нет
    assert [p["name"] for p in data["plan"]] == ["Bench Press", "Old Fly"]
    assert len(data["plan"][0]["sets"]) == 3
    assert data["plan"][0]["sets"][0]["weight"] == Decimal("102.50")


def test_plan_statuses_by_plan_index():
    """Одно упражнение дважды в дне: сделано только то, что сделали."""
    data = _seeded()
    data["exercises"].append(
        {"exercise_id": 1, "exercise_name": "Bench Press", "sets": [], "plan_index": 0}
    )
    assert plan_statuses(data) == [
        ("Bench Press", "done"),
        ("Old Fly", "deleted"),
        ("Bench Press", "todo"),
    ]
    assert plan_todo(data) == [(2, "Bench Press")]


def test_plan_statuses_without_plan():
    assert plan_statuses({"exercises": []}) is None


def test_format_workout_main_with_plan():
    statuses = [("Bench Press", "done"), ("Old Fly", "deleted"), ("Dips <BW>", "todo")]
    exercises = [
        {
            "exercise_name": "Bench Press",
            "notes": None,
            "sets": [{"weight": Decimal("100"), "reps": 5, "seconds": None}],
        }
    ]
    assert format_workout_main(exercises, 12, "Push", statuses) == (
        "<b>Current workout</b> · Push · 12 min\n"
        "\n"
        "✓ Bench Press\n"
        "Old Fly (deleted)\n"
        "— Dips &lt;BW&gt;\n"
        "\n"
        "<b>Bench Press</b>\n"
        "  1. 100kg x 5\n"
    )


def test_format_workout_main_plan_before_first_exercise():
    assert format_workout_main([], 0, "Push", [("Bench Press", "todo")]) == (
        "<b>Current workout</b> · Push · 0 min\n\n— Bench Press\n"
    )


def test_workout_main_kb_plan_buttons():
    assert rows(workout_main_kb([(0, "Bench Press"), (2, "Dips")])) == [
        [("Bench Press", WkPlanEx(index=0).pack())],
        [("Dips", WkPlanEx(index=2).pack())],
        [("Add exercise", "wk_add_exercise"), ("Finish session", "wk_finish")],
        [("Cancel workout", "wk_cancel")],
    ]


# --- хендлеры ---


class FakeMessage:
    def __init__(self, text=None):
        self.text, self.sent = text, []

    async def answer(self, text, reply_markup=None, **kwargs):
        self.sent.append((text, reply_markup))
        return SimpleNamespace(message_id=100 + len(self.sent))

    async def edit_text(self, text, reply_markup=None, **kwargs):
        self.sent.append((text, reply_markup))

    async def edit_reply_markup(self, reply_markup=None):
        pass


class FakeCall:
    def __init__(self):
        self.message, self.alerts = FakeMessage(), []

    async def answer(self, text=None, show_alert=False):
        if text:
            self.alerts.append(text)


class RedisLikeStorage(MemoryStorage):
    async def set_data(self, key, data):
        await super().set_data(key, fsm_json.loads(fsm_json.dumps(data)))


def _state() -> FSMContext:
    return FSMContext(
        storage=RedisLikeStorage(), key=StorageKey(bot_id=1, chat_id=1, user_id=1)
    )


def _with_program(monkeypatch, program):
    async def fake_get_program(session, user_id):
        return program

    monkeypatch.setattr(recording, "get_program", fake_get_program)


def _offer(monkeypatch, program):
    _with_program(monkeypatch, program)
    msg, state = FakeMessage("/workout"), _state()
    asyncio.run(recording.cmd_workout(msg, state, None, USER))
    assert asyncio.run(state.get_state()) is None
    return msg.sent[-1]


def test_workout_offers_next_session_of_week(monkeypatch):
    text, kb = _offer(monkeypatch, _program({(1, 1): False}))
    assert text == "Week 1 of 2 · Next up: <b>Pull</b>. Start it or pick another day:"
    assert rows(kb)[:2] == [
        [("▶ Start Pull", WkDay(program_id=7, week=1, position=2).pack())],
        [("Legs", WkDay(program_id=7, week=1, position=3).pack())],
    ]


def test_workout_offers_only_days_of_current_week(monkeypatch):
    done = {(1, 1): False, (1, 2): True, (1, 3): False, (2, 2): False}
    text, kb = _offer(monkeypatch, _program(done))
    assert "Week 2 of 2 · Next up: <b>Push</b>." in text
    assert rows(kb)[:2] == [
        [("▶ Start Push", WkDay(program_id=7, week=2, position=1).pack())],
        [("Legs", WkDay(program_id=7, week=2, position=3).pack())],
    ]


def test_workout_without_program_starts_free(monkeypatch):
    _with_program(monkeypatch, None)
    shown = []

    async def fake_send(target, state):
        shown.append(workout_main_view(await state.get_data())[0])

    # окно новым сообщением шлёт send_workout_main — по isinstance(Message)
    monkeypatch.setattr(recording, "send_workout_main", fake_send)
    state = _state()
    asyncio.run(recording.cmd_workout(FakeMessage("/workout"), state, None, USER))
    assert shown == ["Workout started. Add your first exercise."]
    assert asyncio.run(state.get_state()) == WorkoutSession.active


def test_day_starts_workout_from_plan(monkeypatch):
    _with_program(monkeypatch, PROGRAM)
    call, state = FakeCall(), _state()
    asyncio.run(
        recording.cb_day(
            call, WkDay(program_id=7, week=1, position=1), state, None, USER
        )
    )
    assert asyncio.run(state.get_state()) == WorkoutSession.active
    data = asyncio.run(state.get_data())
    assert data["program_day"] == "Push" and "started_at" in data
    text, kb = call.message.sent[-1]
    assert text.startswith("<b>Current workout</b> · Push · 0 min")
    assert rows(kb)[0] == [("Bench Press", WkPlanEx(index=0).pack())]


def test_second_tap_on_day_is_ignored(monkeypatch):
    _with_program(monkeypatch, PROGRAM)
    state = _state()
    first, second = (
        WkDay(program_id=7, week=1, position=1),
        WkDay(program_id=7, week=1, position=2),
    )
    asyncio.run(recording.cb_day(FakeCall(), first, state, None, USER))
    asyncio.run(recording.cb_day((call := FakeCall()), second, state, None, USER))
    assert asyncio.run(state.get_data())["program_day"] == "Push"
    assert call.message.sent == []


@pytest.mark.parametrize(
    ("program", "day"),
    [
        (
            None,
            WkDay(program_id=7, week=1, position=1),
        ),  # программу заменили или удалили
        (PROGRAM, WkDay(program_id=7, week=2, position=1)),  # неделя 1 ещё не пройдена
        (
            _program({(1, 1): False}),
            WkDay(program_id=7, week=1, position=1),
        ),  # уже сделан
    ],
)
def test_unavailable_day_is_refused(monkeypatch, program, day):
    _with_program(monkeypatch, program)
    call, state = FakeCall(), _state()
    asyncio.run(recording.cb_day(call, day, state, None, USER))
    assert call.alerts == ["This day is no longer available. Use /workout again."]
    assert asyncio.run(state.get_state()) is None


def test_free_workout(monkeypatch):
    call, state = FakeCall(), _state()
    asyncio.run(recording.cb_free(call, state))
    assert asyncio.run(state.get_state()) == WorkoutSession.active
    assert "plan" not in asyncio.run(state.get_data())
    assert call.message.sent[-1][0] == "Workout started. Add your first exercise."


# --- экран упражнения из плана ---

PLAN_SETS = [
    {"weight": Decimal("100"), "reps": 5, "seconds": None},
    {"weight": Decimal("100"), "reps": 5, "seconds": None},
    {"weight": Decimal("80"), "reps": 8, "seconds": None},
]
MANUAL = {"weight": Decimal("95"), "reps": 5, "seconds": None}


def test_toggle_checks_and_unchecks():
    current = []
    toggle_plan_set(current, PLAN_SETS, 2)
    assert current == [{**PLAN_SETS[2], "plan_idx": 2}]
    toggle_plan_set(current, PLAN_SETS, 2)
    assert current == []


def test_untoggle_keeps_manual_sets():
    current = []
    toggle_plan_set(current, PLAN_SETS, 0)
    current.append(dict(MANUAL))
    toggle_plan_set(current, PLAN_SETS, 1)
    toggle_plan_set(current, PLAN_SETS, 0)
    assert current == [MANUAL, {**PLAN_SETS[1], "plan_idx": 1}]


def test_set_entered_kb_plan_buttons():
    kb = set_entered_kb(plan=["100x5", "100x5", "80x8", "BWx1:30"], checked={1})
    assert rows(kb) == [
        [
            ("100x5", WkPlanSet(idx=0).pack()),
            ("✓ 100x5", WkPlanSet(idx=1).pack()),
            ("80x8", WkPlanSet(idx=2).pack()),
        ],
        [("BWx1:30", WkPlanSet(idx=3).pack())],
        [("Finish exercise", "wk_finish_exercise")],
        [("Cancel exercise", "wk_cancel_exercise")],
    ]


def test_set_entered_kb_without_plan_unchanged():
    assert rows(set_entered_kb(has_notes=True)) == [
        [("Finish exercise", "wk_finish_exercise")],
        [("Remove note", "wk_remove_note")],
        [("Cancel exercise", "wk_cancel_exercise")],
    ]


def test_format_current_sets_with_plan():
    text = format_current_sets(
        "Bench Press",
        "felt easy",
        [SetEntry(Decimal("100"), 5)],
        plan_line="100x5, 100x5",
        hint="pause <2s>",
    )
    assert text == (
        "<b>Bench Press</b>\n"
        "Plan: 100x5, 100x5\n"
        "Tip: pause &lt;2s&gt;\n"
        "<i>felt easy</i>\n"
        "\n"
        "1. 100kg x 5\n"
        "\n"
        "Tap a planned set once done, or enter a set or a note:"
    )


class FakeCatalog:
    def __init__(self, session):
        pass

    async def get_visible(self, exercise_id, user_id):
        names = {1: "Bench Press", 5: "Row", 6: "Squat"}
        if exercise_id in names:
            return ExerciseInfo(exercise_id, names[exercise_id])
        return None


async def _day_started(monkeypatch, state):
    _with_program(monkeypatch, PROGRAM)
    monkeypatch.setattr(recording, "Catalog", FakeCatalog)
    await recording.cb_day(
        FakeCall(), WkDay(program_id=7, week=1, position=1), state, None, USER
    )


def _open_plan_exercise(monkeypatch, index):
    state = _state()
    asyncio.run(_day_started(monkeypatch, state))
    call = FakeCall()
    asyncio.run(
        recording.cb_plan_exercise(call, WkPlanEx(index=index), state, None, USER)
    )
    return state, call


def test_plan_exercise_opens_with_plan(monkeypatch):
    state, call = _open_plan_exercise(monkeypatch, 0)
    assert asyncio.run(state.get_state()) == WorkoutSession.entering_sets
    data = asyncio.run(state.get_data())
    assert (data["current_exercise_id"], data["current_plan_index"]) == (1, 0)
    text, kb = call.message.sent[-1]
    assert "Plan: 100x5, 100x5" in text and "Tip: pause" in text
    assert rows(kb)[0] == [
        ("100x5", WkPlanSet(idx=0).pack()),
        ("100x5", WkPlanSet(idx=1).pack()),
    ]


def test_plan_set_tap_checks_it(monkeypatch):
    state, _ = _open_plan_exercise(monkeypatch, 0)
    call = FakeCall()
    asyncio.run(recording.cb_plan_set(call, WkPlanSet(idx=1), state))
    data = asyncio.run(state.get_data())
    assert data["current_sets"] == [
        {"weight": Decimal("100.00"), "reps": 5, "seconds": None, "plan_idx": 1}
    ]
    assert rows(call.message.sent[-1][1])[0][1] == ("✓ 100x5", WkPlanSet(idx=1).pack())


def test_finish_plan_exercise_records_plan_index(monkeypatch):
    state, _ = _open_plan_exercise(monkeypatch, 2)
    asyncio.run(recording.cb_plan_set(FakeCall(), WkPlanSet(idx=0), state))
    asyncio.run(recording.cb_finish_exercise(FakeCall(), state))
    data = asyncio.run(state.get_data())
    assert data["exercises"] == [
        {
            "exercise_id": 1,
            "exercise_name": "Bench Press",
            "sets": [{"weight": Decimal("80.00"), "reps": 10, "seconds": None}],
            "notes": None,
            "plan_index": 2,
        }
    ]
    assert plan_todo(data) == [(0, "Bench Press")]
    assert data["current_plan_index"] is None


def test_finish_plan_exercise_without_sets_is_skip(monkeypatch):
    state, _ = _open_plan_exercise(monkeypatch, 0)
    call = FakeCall()
    asyncio.run(recording.cb_finish_exercise(call, state))
    assert call.alerts == []
    assert asyncio.run(state.get_state()) == WorkoutSession.active
    data = asyncio.run(state.get_data())
    assert data["exercises"] == []
    assert plan_todo(data) == [(0, "Bench Press"), (2, "Bench Press")]


def test_finish_plan_exercise_with_note_warns(monkeypatch):
    """Заметка без подходов не должна молча пропасть при пропуске упражнения."""
    state, _ = _open_plan_exercise(monkeypatch, 0)
    asyncio.run(state.update_data(current_notes="shoulder hurts"))
    call = FakeCall()
    asyncio.run(recording.cb_finish_exercise(call, state))
    assert call.alerts == [
        "Add a set, or remove the note: it isn't saved without sets."
    ]
    assert asyncio.run(state.get_state()) == WorkoutSession.entering_sets
    assert asyncio.run(state.get_data())["current_notes"] == "shoulder hurts"


def test_done_plan_exercise_button_is_ignored(monkeypatch):
    state, _ = _open_plan_exercise(monkeypatch, 0)
    asyncio.run(recording.cb_plan_set(FakeCall(), WkPlanSet(idx=0), state))
    asyncio.run(recording.cb_finish_exercise(FakeCall(), state))
    again = FakeCall()
    asyncio.run(recording.cb_plan_exercise(again, WkPlanEx(index=0), state, None, USER))
    assert asyncio.run(state.get_state()) == WorkoutSession.active
    assert again.message.sent == []


def test_free_exercise_after_cancelled_plan_one_has_no_plan(monkeypatch):
    state, _ = _open_plan_exercise(monkeypatch, 0)
    asyncio.run(recording.cb_cancel_exercise(FakeCall(), state))
    data = asyncio.run(state.get_data())
    assert data["current_plan_index"] is None
    assert data["current_plan_sets"] is None


def test_next_exercise_starts_without_previous_sets(monkeypatch):
    """MemoryStorage не копирует вложенные списки: сброс упражнения не должен
    класть в черновик общий объект, иначе подходы переедут к следующему."""
    state = FSMContext(
        storage=MemoryStorage(), key=StorageKey(bot_id=1, chat_id=1, user_id=1)
    )
    asyncio.run(_day_started(monkeypatch, state))
    open_ex = recording.cb_plan_exercise
    asyncio.run(open_ex(FakeCall(), WkPlanEx(index=0), state, None, USER))
    asyncio.run(recording.cb_plan_set(FakeCall(), WkPlanSet(idx=0), state))
    asyncio.run(recording.cb_finish_exercise(FakeCall(), state))
    asyncio.run(open_ex(FakeCall(), WkPlanEx(index=2), state, None, USER))
    assert asyncio.run(state.get_data())["current_sets"] == []


# --- пропуск дня и конец программы ---

ALL_BUT_LAST = {
    (1, 1): False,
    (1, 2): False,
    (1, 3): True,
    (2, 1): False,
    (2, 2): False,
}


def _with_completion(monkeypatch, program):
    calls = []

    async def fake_complete(session, user_id, program_id, week, day_position, skipped):
        calls.append((user_id, program_id, week, day_position, skipped))
        program.done[(week, day_position)] = skipped
        return program

    monkeypatch.setattr(recording, "complete_session", fake_complete)
    return calls


def _skip(monkeypatch, program, week, position):
    _with_program(monkeypatch, program)
    calls = _with_completion(monkeypatch, program)
    call = FakeCall()
    asyncio.run(
        recording.cb_skip(
            call,
            WkSkip(program_id=7, week=week, position=position),
            _state(),
            None,
            USER,
        )
    )
    return calls, call


def test_day_choice_kb_has_skip():
    days = [(1, "Push"), (3, "Legs")]
    assert rows(day_choice_kb(7, 1, days, next_position=1))[-1] == [
        ("Skip Push", WkSkip(program_id=7, week=1, position=1).pack()),
        ("Free workout", "wk_free"),
    ]


def test_skip_marks_session_and_redraws(monkeypatch):
    calls, call = _skip(monkeypatch, _program(), 1, 1)
    assert calls == [(42, 7, 1, 1, True)]
    text, kb = call.message.sent[-1]
    assert text.startswith("Week 1 of 2 · Next up: <b>Pull</b>.")
    assert rows(kb)[0] == [
        ("▶ Start Pull", WkDay(program_id=7, week=1, position=2).pack())
    ]


def test_skip_of_not_next_session_is_ignored(monkeypatch):
    calls, call = _skip(monkeypatch, _program(), 1, 2)
    assert calls == []
    assert call.message.sent == []


def test_skip_of_last_session_finishes_program(monkeypatch):
    calls, call = _skip(monkeypatch, _program(dict(ALL_BUT_LAST)), 2, 3)
    assert calls == [(42, 7, 2, 3, True)]
    assert call.message.sent[-1] == (PROGRAM_FINISHED, None)


def test_last_week_line(monkeypatch):
    done = {(1, 1): False, (1, 2): False, (1, 3): False}
    text, _ = _offer(monkeypatch, _program(done))
    assert text.startswith(f"{LAST_WEEK}\n\nWeek 2 of 2 · Next up: <b>Push</b>.")


def test_first_week_has_no_last_week_line(monkeypatch):
    text, _ = _offer(monkeypatch, _program())
    assert LAST_WEEK not in text


def test_finished_program_starts_free_workout(monkeypatch):
    done = {**ALL_BUT_LAST, (2, 3): False}
    _with_program(monkeypatch, _program(done))
    shown = []

    async def fake_send(target, state):
        shown.append(workout_main_view(await state.get_data())[0])

    monkeypatch.setattr(recording, "send_workout_main", fake_send)
    msg, state = FakeMessage("/workout"), _state()
    asyncio.run(recording.cmd_workout(msg, state, None, USER))
    assert msg.sent[-1][0] == PROGRAM_FINISHED
    assert shown == ["Workout started. Add your first exercise."]
    assert "plan" not in asyncio.run(state.get_data())


def test_skip_from_replaced_program_is_ignored(monkeypatch):
    """Старый экран недели после нового импорта: позиции совпадают, программа — нет."""
    _with_program(monkeypatch, _program())
    calls = _with_completion(monkeypatch, _program())
    call = FakeCall()
    stale = WkSkip(program_id=6, week=1, position=1)
    asyncio.run(recording.cb_skip(call, stale, _state(), None, USER))
    assert calls == []
    assert call.message.sent == []


def test_day_from_replaced_program_is_refused(monkeypatch):
    _with_program(monkeypatch, _program())
    call, state = FakeCall(), _state()
    stale = WkDay(program_id=6, week=1, position=1)
    asyncio.run(recording.cb_day(call, stale, state, None, USER))
    assert call.alerts == ["This day is no longer available. Use /workout again."]
    assert asyncio.run(state.get_state()) is None

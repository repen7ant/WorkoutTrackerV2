import asyncio
from decimal import Decimal

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from bot.programs.repository import StoredDay, StoredExercise, StoredProgram
from bot.users.models import User
from bot.utils import fsm_json
from bot.workouts.domain import SetEntry
from bot.workouts.draft import plan_statuses, plan_todo, seed_plan
from bot.workouts.formatters import format_workout_main
from bot.workouts.handlers import recording
from bot.workouts.handlers.common import workout_main_view
from bot.workouts.keyboards import WkDay, WkPlanEx, day_choice_kb, workout_main_kb
from bot.workouts.states import WorkoutSession

BENCH_SETS = [SetEntry(Decimal("100.00"), 5), SetEntry(Decimal("100.00"), 5)]
PROGRAM = StoredProgram(
    id=7,
    next_position=2,
    days=[
        StoredDay(
            1,
            "Push",
            [
                StoredExercise(1, "Bench Press", "pause", BENCH_SETS),
                StoredExercise(None, "Old Fly", None, [SetEntry(None, 12)]),
                StoredExercise(1, "Bench Press", None, [SetEntry(Decimal("80"), 10)]),
            ],
        ),
        StoredDay(2, "Pull", [StoredExercise(5, "Row", None, [SetEntry(None, 8)])]),
        StoredDay(3, "Legs", [StoredExercise(6, "Squat", None, [SetEntry(None, 5)])]),
    ],
)
USER = User(id=42)


def rows(kb):
    return [[(b.text, b.callback_data) for b in row] for row in kb.inline_keyboard]


def _seeded(position=1) -> dict:
    data = {"exercises": []}
    seed_plan(data, PROGRAM, position)
    return fsm_json.loads(fsm_json.dumps(data))


def test_day_choice_kb_order():
    days = [(d.position, d.name) for d in PROGRAM.days]
    assert rows(day_choice_kb(days, next_position=2)) == [
        [("▶ Start Pull", WkDay(position=2).pack())],
        [("Push", WkDay(position=1).pack()), ("Legs", WkDay(position=3).pack())],
        [("Free workout", "wk_free")],
    ]


def test_day_choice_kb_stale_next_position():
    days = [(d.position, d.name) for d in PROGRAM.days]
    assert rows(day_choice_kb(days, next_position=9))[0] == [
        ("▶ Start Push", WkDay(position=1).pack())
    ]


def test_seed_plan_marks_deleted():
    data = _seeded()
    assert (data["program_id"], data["program_day"], data["program_day_position"]) == (
        7,
        "Push",
        1,
    )
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

    async def edit_text(self, text, reply_markup=None, **kwargs):
        self.sent.append((text, reply_markup))


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


def test_workout_offers_next_day(monkeypatch):
    _with_program(monkeypatch, PROGRAM)
    msg, state = FakeMessage("/workout"), _state()
    asyncio.run(recording.cmd_workout(msg, state, None, USER))
    text, kb = msg.sent[-1]
    assert text == "Next up: <b>Pull</b>. Start it or pick another day:"
    assert rows(kb)[0] == [("▶ Start Pull", WkDay(position=2).pack())]
    assert asyncio.run(state.get_state()) is None


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
    asyncio.run(recording.cb_day(call, WkDay(position=1), state, None, USER))
    assert asyncio.run(state.get_state()) == WorkoutSession.active
    data = asyncio.run(state.get_data())
    assert data["program_day"] == "Push" and "started_at" in data
    text, kb = call.message.sent[-1]
    assert text.startswith("<b>Current workout</b> · Push · 0 min")
    assert rows(kb)[0] == [("Bench Press", WkPlanEx(index=0).pack())]


def test_second_tap_on_day_is_ignored(monkeypatch):
    _with_program(monkeypatch, PROGRAM)
    state = _state()
    asyncio.run(recording.cb_day(FakeCall(), WkDay(position=1), state, None, USER))
    second = FakeCall()
    asyncio.run(recording.cb_day(second, WkDay(position=2), state, None, USER))
    assert asyncio.run(state.get_data())["program_day"] == "Push"
    assert second.message.sent == []


def test_day_of_replaced_program(monkeypatch):
    _with_program(monkeypatch, None)
    call, state = FakeCall(), _state()
    asyncio.run(recording.cb_day(call, WkDay(position=1), state, None, USER))
    assert call.alerts == ["The program has changed. Use /workout again."]
    assert asyncio.run(state.get_state()) is None


def test_free_workout(monkeypatch):
    call, state = FakeCall(), _state()
    asyncio.run(recording.cb_free(call, state))
    assert asyncio.run(state.get_state()) == WorkoutSession.active
    assert "plan" not in asyncio.run(state.get_data())
    assert call.message.sent[-1][0] == "Workout started. Add your first exercise."

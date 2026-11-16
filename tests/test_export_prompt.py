import asyncio
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from bot.export import handlers
from bot.export.keyboards import export_period_kb, wishes_kb
from bot.export.prompt import build_ai_prompt
from bot.export.service import ExportExercise, ExportWorkout
from bot.export.states import ExportStates
from bot.programs.parser import FORMAT_DESCRIPTION, PROGRAM_MARKER
from bot.programs.repository import StoredDay, StoredExercise, StoredProgram
from bot.users.models import User
from bot.workouts.domain import SetEntry

PROGRAM_TEXT = "# PROGRAM\n== Pull ==\nRow: 60x10, 60x10"


def _workout(program_day=None, notes=None) -> ExportWorkout:
    workout = ExportWorkout(
        date=date(2026, 1, 1),
        start_time=None,
        end_time=None,
        notes=notes,
        exercises=[
            ExportExercise(
                name="Row",
                muscles=["Back"],
                sets=[SetEntry.create(Decimal("60"), 10)],
                notes=None,
            )
        ],
    )
    if program_day is not None:
        workout["program_day"] = program_day
    return workout


def _prompt(**kwargs) -> str:
    workouts = kwargs.pop("workouts", [_workout()])
    return build_ai_prompt(workouts, "all time", None, date(2026, 1, 2), **kwargs)


def _section(prompt: str, title: str) -> str:
    """Текст секции до следующего заголовка «## »."""
    after = prompt.split(f"\n{title}\n", 1)[1]
    return after.split("\n## ", 1)[0]


def test_prompt_with_wishes_and_program():
    prompt = _prompt(
        workouts=[_workout(program_day="Pull")],
        wishes="Full body please.\nNo leg press in my gym.",
        program_text=PROGRAM_TEXT,
    )
    titles = [line for line in prompt.splitlines() if line.startswith("## ")]
    assert titles == [
        "## CONTEXT",
        "## EXERCISES",
        "## CURRENT PROGRAM",
        "## DATA",
        "## ATHLETE REQUESTS",
        "## TASK",
        "## OUTPUT",
    ]
    assert PROGRAM_TEXT in _section(prompt, "## CURRENT PROGRAM")
    requests = _section(prompt, "## ATHLETE REQUESTS")
    assert "Full body please.\nNo leg press in my gym." in requests
    task = _section(prompt, "## TASK")
    assert "5. Plan versus actual" in task
    assert "6. Program restructuring" in task
    assert FORMAT_DESCRIPTION in _section(prompt, "## OUTPUT")


def test_prompt_without_program_or_wishes():
    prompt = _prompt()
    assert "## CURRENT PROGRAM" not in prompt
    assert "## ATHLETE REQUESTS" not in prompt
    assert "Plan versus actual" not in prompt
    assert "| day:" not in prompt and "`day:`" not in prompt
    assert "5. Program restructuring" in _section(prompt, "## TASK")
    # первую программу ИИ тоже должен выдать блоком для импорта
    assert FORMAT_DESCRIPTION in _section(prompt, "## OUTPUT")
    assert prompt.rstrip().endswith(FORMAT_DESCRIPTION.splitlines()[-1])


def test_day_in_workout_header():
    lines = _prompt(
        workouts=[_workout(program_day="Pull", notes="tired")],
        program_text=PROGRAM_TEXT,
    ).splitlines()
    assert "2026-01-01 | day: Pull | notes: tired" in lines
    assert any("`day:`" in line for line in lines)


def test_day_of_deleted_program_is_still_explained():
    prompt = _prompt(workouts=[_workout(program_day="Pull")])
    assert "2026-01-01 | day: Pull" in prompt.splitlines()
    assert any("`day:`" in line for line in prompt.splitlines())
    assert "## CURRENT PROGRAM" not in prompt


def test_prompt_lists_rest_of_catalog():
    prompt = _prompt(
        available={"row": ["Back"], "Squat": ["Glutes", "Quads"], "Plank": []}
    )
    section = _section(prompt, "## AVAILABLE EXERCISES")
    assert "Plank — muscle groups not set\nSquat — Glutes, Quads" in section
    # уже есть в EXERCISES — второй раз не нужен
    assert "row" not in section.lower().split("\n", 1)[1]
    titles = [line for line in prompt.splitlines() if line.startswith("## ")]
    assert titles.index("## AVAILABLE EXERCISES") == titles.index("## EXERCISES") + 1
    assert "AVAILABLE EXERCISES" in _section(prompt, "## OUTPUT")


def test_prompt_without_rest_of_catalog():
    assert "## AVAILABLE EXERCISES" not in _prompt(available={"Row": ["Back"]})


@pytest.mark.parametrize(
    ("has_previous", "labels"),
    [(True, ["Keep previous", "Skip", "Cancel"]), (False, ["Skip", "Cancel"])],
)
def test_wishes_kb(has_previous, labels):
    kb = wishes_kb(has_previous)
    assert [b.text for row in kb.inline_keyboard for b in row] == labels


# --- шаг пожеланий ---


class FakeMessage:
    def __init__(self, text=None):
        self.text, self.sent, self.documents = text, [], []

    async def answer(self, text, reply_markup=None, **kwargs):
        self.sent.append((text, reply_markup))
        return SimpleNamespace(message_id=1)

    async def edit_text(self, text, reply_markup=None, **kwargs):
        self.sent.append((text, reply_markup))

    async def answer_document(self, document, caption=None, **kwargs):
        self.documents.append((document.data.decode(), caption))


class FakeCall:
    def __init__(self, message=None):
        self.message, self.alerts = message or FakeMessage(), []

    async def answer(self, text=None, show_alert=False):
        if text:
            self.alerts.append(text)


class FakeSession:
    commits = 0

    async def commit(self):
        self.commits += 1


@pytest.fixture
def export(monkeypatch):
    async def fake_collect(session, user_id, since):
        return [_workout()]

    async def fake_get_program(session, user_id):
        return None

    async def fake_catalog(session, user_id):
        return {"Row": ["Back"], "Deadlift": ["Back", "Glutes"]}

    monkeypatch.setattr(handlers, "catalog_exercises", fake_catalog)
    monkeypatch.setattr(handlers, "collect_workouts", fake_collect)
    monkeypatch.setattr(handlers, "get_program", fake_get_program)
    state = FSMContext(
        storage=MemoryStorage(),
        key=StorageKey(bot_id=1, chat_id=1, user_id=1, destiny="exercises"),
    )
    return state, FakeSession()


def _user(wishes=None):
    return User(id=42, utc_offset=180, ai_wishes=wishes)


def _ask(state, session, user):
    call = FakeCall()
    asyncio.run(
        handlers.cb_export_period(
            call, handlers.ExportPeriod(period="month"), state, session, user
        )
    )
    return call


def test_period_asks_for_wishes(export):
    state, session = export
    user = _user("2.5 kg plates")
    call = _ask(state, session, user)
    text, kb = call.message.sent[-1]
    assert text.startswith("Any requests for the AI?")
    assert "2.5 kg plates" in text
    assert kb.inline_keyboard[0][0].text == "Keep previous"
    assert asyncio.run(state.get_state()) == ExportStates.entering_wishes


def test_typed_wishes_are_saved_and_exported(export):
    state, session = export
    user = _user("old")
    _ask(state, session, user)
    msg = FakeMessage("Full body, 3 days a week")
    asyncio.run(handlers.on_wishes(msg, state, session, user))
    assert user.ai_wishes == "Full body, 3 days a week"
    assert session.commits == 1
    prompt, caption = msg.documents[-1]
    assert "Full body, 3 days a week" in _section(prompt, "## ATHLETE REQUESTS")
    assert "Deadlift — Back, Glutes" in _section(prompt, "## AVAILABLE EXERCISES")
    assert PROGRAM_MARKER in caption
    assert asyncio.run(state.get_state()) is None


def test_too_long_wishes_are_refused(export):
    state, session = export
    user = _user()
    _ask(state, session, user)
    msg = FakeMessage("x" * 1001)
    asyncio.run(handlers.on_wishes(msg, state, session, user))
    assert msg.documents == []
    assert "1000" in msg.sent[-1][0]
    assert asyncio.run(state.get_state()) == ExportStates.entering_wishes


def test_keep_previous_wishes(export):
    state, session = export
    user = _user("no leg press")
    _ask(state, session, user)
    call = FakeCall()
    asyncio.run(handlers.cb_wishes_keep(call, state, session, user))
    prompt, _ = call.message.documents[-1]
    assert "no leg press" in _section(prompt, "## ATHLETE REQUESTS")
    assert session.commits == 0


def test_skip_clears_wishes(export):
    state, session = export
    user = _user("no leg press")
    _ask(state, session, user)
    call = FakeCall()
    asyncio.run(handlers.cb_wishes_skip(call, state, session, user))
    prompt, _ = call.message.documents[-1]
    assert "## ATHLETE REQUESTS" not in prompt
    assert user.ai_wishes is None
    assert session.commits == 1


def test_prompt_program_progress():
    prompt = _prompt(
        program_text=PROGRAM_TEXT,
        program_progress="Week 2 of 4 · 5 of 12 sessions done",
    )
    section = _section(prompt, "## CURRENT PROGRAM")
    assert "Progress: Week 2 of 4 · 5 of 12 sessions done" in section


def test_day_with_week_in_header():
    workout = _workout(program_day="Pull", notes="tired")
    workout["program_week"] = 2
    lines = _prompt(workouts=[workout], program_text=PROGRAM_TEXT).splitlines()
    assert "2026-01-01 | day: Pull (week 2) | notes: tired" in lines


def test_restructuring_asks_for_a_cycle_of_weeks():
    task = _section(_prompt(), "## TASK")
    assert "weeks" in task.split("Program restructuring", 1)[1]


# --- период «текущая программа» ---


def _labels(kb):
    return [b.text for row in kb.inline_keyboard for b in row]


PERIOD_LABELS = ["Last month", "Last 3 months", "Last 6 months", "All time", "Cancel"]


@pytest.mark.parametrize(
    ("has_program", "labels"),
    [(True, ["Current program", *PERIOD_LABELS]), (False, PERIOD_LABELS)],
)
def test_export_period_kb(has_program, labels):
    assert _labels(export_period_kb(has_program)) == labels


# 01:30 11 ноября по UTC+3
IMPORTED = datetime(2026, 11, 10, 22, 30, tzinfo=UTC)


def _imported_program():
    day = StoredDay(1, "Pull", [StoredExercise(5, "Row", None, [[SetEntry(None, 8)]])])
    return StoredProgram(id=1, weeks=1, days=[day], done={}, imported_at=IMPORTED)


def _with_program(monkeypatch, program):
    seen = []

    async def fake_get_program(session, user_id):
        return program

    async def fake_collect(session, user_id, since):
        seen.append(since)
        return [_workout()]

    monkeypatch.setattr(handlers, "get_program", fake_get_program)
    monkeypatch.setattr(handlers, "collect_workouts", fake_collect)
    return seen


def test_export_menu_offers_program_period(export, monkeypatch):
    _, session = export
    _with_program(monkeypatch, _imported_program())
    msg = FakeMessage("/export")
    asyncio.run(handlers.cmd_export(msg, session, _user()))
    assert _labels(msg.sent[-1][1])[0] == "Current program"


def test_program_period_exports_since_import(export, monkeypatch):
    state, session = export
    seen = _with_program(monkeypatch, _imported_program())
    period = handlers.ExportPeriod(period="program")
    asyncio.run(handlers.cb_export_period(FakeCall(), period, state, session, _user()))
    call = FakeCall()
    asyncio.run(handlers.cb_wishes_skip(call, state, session, _user()))
    assert seen == [date(2026, 11, 11)] * 2
    prompt, _ = call.message.documents[-1]
    assert "Period: current program (2026-11-11 … " in prompt


def test_program_period_without_program(export):
    state, session = export
    call = FakeCall()
    period = handlers.ExportPeriod(period="program")
    asyncio.run(handlers.cb_export_period(call, period, state, session, _user()))
    assert call.alerts == ["No program."]
    assert asyncio.run(state.get_state()) is None

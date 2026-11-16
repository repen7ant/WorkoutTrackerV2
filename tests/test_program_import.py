import asyncio
from decimal import Decimal

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from bot.catalog.api import ExerciseInfo, rank_similar
from bot.programs.domain import InvalidProgram
from bot.programs.draft import decode_txt, plan_from_fsm, plan_to_fsm
from bot.programs.handlers import import_
from bot.programs.keyboards import ImportPick, confirm_kb, match_kb
from bot.programs.parser import parse_program
from bot.programs.states import ProgramImport
from bot.users.models import User
from bot.utils import fsm_json

PROGRAM = """# PROGRAM
== Push ==
Bench Press: 100x5, 102.5x5 | notes: pause
Plank: BWx1:30
== Pull ==
Romanian Deadlift: 80x8
plank: BWx1:00
"""

BENCH = ExerciseInfo(1, "Bench Press")
RDL = ExerciseInfo(3, "RDL")
USER = User(id=42)


def rows(kb):
    return [[(b.text, b.callback_data) for b in row] for row in kb.inline_keyboard]


def test_plan_fsm_round_trip():
    plan = parse_program(PROGRAM)
    stored = fsm_json.loads(fsm_json.dumps(plan_to_fsm(plan)))
    assert plan_from_fsm(stored) == plan
    assert plan_from_fsm(stored).days[0].exercises[0].sets[1].weight == Decimal(
        "102.50"
    )


def test_decode_txt_rejects_non_utf8():
    with pytest.raises(InvalidProgram):
        decode_txt("# PROGRAM\nЖим: 100x5".encode("cp1251"))


def test_decode_txt_strips_bom():
    # Блокнот Windows ставит BOM — без этого маркер не узнать
    assert decode_txt("﻿# PROGRAM".encode()) == "# PROGRAM"


def test_match_kb_buttons():
    assert rows(match_kb([BENCH, RDL], left=2)) == [
        [("Bench Press", ImportPick(exercise_id=1, left=2).pack())],
        [("RDL", ImportPick(exercise_id=3, left=2).pack())],
        [("Create new", "pi_create")],
        [("Cancel import", "pi_cancel")],
    ]


@pytest.mark.parametrize(
    ("replacing", "label"),
    [(False, "Save program"), (True, "Replace current program")],
)
def test_confirm_kb_replacing_label(replacing, label):
    assert rows(confirm_kb(replacing)) == [
        [(label, "pi_save")],
        [("Cancel import", "pi_cancel")],
    ]


def test_rank_similar_by_shared_words():
    catalog = [
        ExerciseInfo(1, "Bench Press"),
        ExerciseInfo(2, "Back Squat"),
        ExerciseInfo(3, "Barbell Bench Press"),
        ExerciseInfo(4, "Leg Press"),
    ]
    assert rank_similar("Barbell Back Squats", catalog) == [
        ExerciseInfo(2, "Back Squat"),
        ExerciseInfo(3, "Barbell Bench Press"),
    ]


def test_rank_similar_prefers_fewer_extra_words():
    catalog = [
        ExerciseInfo(1, "Dumbbell Romanian Deadlift"),
        ExerciseInfo(2, "Romanian Deadlift"),
    ]
    assert rank_similar("Romanian Deadlift Smith", catalog)[0] == ExerciseInfo(
        2, "Romanian Deadlift"
    )


# --- мастер ---


class SentMessage:
    def __init__(self, message_id, text, kb):
        self.message_id, self.text, self.kb = message_id, text, kb


class FakeBot:
    def __init__(self):
        self.stripped = []

    async def edit_message_reply_markup(self, chat_id, message_id, reply_markup=None):
        self.stripped.append(message_id)


class FakeChat:
    id = 1


class FakeMessage:
    def __init__(self, text=None, bot=None):
        self.text, self.bot, self.chat = text, bot or FakeBot(), FakeChat()
        self.sent: list[SentMessage] = []
        self.message_id = 100

    async def answer(self, text, reply_markup=None, **kwargs):
        msg = SentMessage(200 + len(self.sent), text, reply_markup)
        self.sent.append(msg)
        return msg

    async def edit_text(self, text, reply_markup=None, **kwargs):
        self.sent.append(SentMessage(self.message_id, text, reply_markup))

    async def edit_reply_markup(self, reply_markup=None):
        pass


class FakeCall:
    def __init__(self, message):
        self.message, self.alerts = message, []

    async def answer(self, text=None, show_alert=False):
        if text:
            self.alerts.append(text)


CATALOG = {1: BENCH, 2: ExerciseInfo(2, "Plank"), 3: RDL}


class FakeCatalog:
    def __init__(self, session):
        self.exercises = CATALOG

    async def by_names(self, names, user_id):
        index = {ex.name.casefold(): ex for ex in self.exercises.values()}
        return {n: index[n.casefold()] for n in names if n.casefold() in index}

    async def similar(self, name, user_id, limit=5):
        return [RDL] if "dead" in name.casefold() else []

    async def search(self, query, user_id, limit=20):
        found = [
            ex
            for ex in self.exercises.values()
            if query.casefold() in ex.name.casefold()
        ]
        return found, len(found)

    async def get_visible(self, exercise_id, user_id):
        return self.exercises.get(exercise_id)


@pytest.fixture
def wizard(monkeypatch):
    saved = {}

    async def fake_get_program(session, user_id):
        return saved.get("existing")

    async def fake_import(session, user_id, plan, exercise_ids):
        saved["imported"] = (user_id, plan, exercise_ids)

    monkeypatch.setattr(import_, "Catalog", FakeCatalog)
    monkeypatch.setattr(import_, "get_program", fake_get_program)
    monkeypatch.setattr(import_, "import_program", fake_import)
    state = FSMContext(
        storage=MemoryStorage(),
        key=StorageKey(bot_id=1, chat_id=1, user_id=1, destiny="exercises"),
    )
    return state, saved


def test_parse_error_reports_line(wizard):
    state, _ = wizard
    msg = FakeMessage("# PROGRAM\n== Push ==\nBench 100 5")
    asyncio.run(import_.on_program_text(msg, state, None, USER))
    assert msg.sent[-1].text == (
        'Can\'t import program.\nline 3: expected "Exercise: sets", got "Bench 100 5"'
    )
    assert asyncio.run(state.get_state()) is None


def test_long_message_asks_for_file(wizard):
    state, _ = wizard
    msg = FakeMessage(PROGRAM + "Dips: BWx5\n" * 400)
    asyncio.run(import_.on_program_text(msg, state, None, USER))
    assert ".txt" in msg.sent[-1].text
    assert asyncio.run(state.get_state()) is None


def test_wizard_asks_unmatched_then_saves(wizard):
    state, saved = wizard
    msg = FakeMessage(PROGRAM)
    asyncio.run(import_.on_program_text(msg, state, None, USER))

    question = msg.sent[-1]
    assert question.text.startswith(
        'Exercise "Romanian Deadlift" is not in your catalog'
    )
    assert rows(question.kb)[0] == [("RDL", ImportPick(exercise_id=3, left=1).pack())]
    assert asyncio.run(state.get_state()) == ProgramImport.matching

    call = FakeCall(FakeMessage())
    asyncio.run(
        import_.cb_pick(call, ImportPick(exercise_id=3, left=1), state, None, USER)
    )
    summary = call.message.sent[-1]
    assert summary.text == "Program: 2 days — Push (2), Pull (2).\nSave it?"
    assert rows(summary.kb) == rows(confirm_kb(replacing=False))

    save = FakeCall(FakeMessage())
    asyncio.run(import_.cb_save(save, state, None, USER))
    user_id, plan, exercise_ids = saved["imported"]
    assert (user_id, plan) == (42, parse_program(PROGRAM))
    assert exercise_ids == {"bench press": 1, "plank": 2, "romanian deadlift": 3}
    assert save.message.sent[-1].text == "Program saved. Start it with /workout."
    assert asyncio.run(state.get_state()) is None


def test_pick_of_unavailable_exercise_is_refused(wizard):
    state, _ = wizard
    asyncio.run(import_.on_program_text(FakeMessage(PROGRAM), state, None, USER))
    call = FakeCall(FakeMessage())
    asyncio.run(
        import_.cb_pick(call, ImportPick(exercise_id=99, left=1), state, None, USER)
    )
    assert call.alerts == ["Exercise not found."]
    assert asyncio.run(state.get_data())["pending"] == ["Romanian Deadlift"]


def test_double_tap_pick_is_ignored(wizard):
    """Второй тап по старой кнопке не должен сопоставить следующее название."""
    state, _ = wizard
    text = PROGRAM + "== Legs ==\nHack Squat: 100x8\n"
    asyncio.run(import_.on_program_text(FakeMessage(text), state, None, USER))
    first = ImportPick(exercise_id=3, left=2)
    asyncio.run(import_.cb_pick(FakeCall(FakeMessage()), first, state, None, USER))
    asyncio.run(import_.cb_pick(FakeCall(FakeMessage()), first, state, None, USER))
    data = asyncio.run(state.get_data())
    assert data["pending"] == ["Hack Squat"]
    assert "hack squat" not in data["matched"]


def test_typed_search_offers_results(wizard):
    state, _ = wizard
    asyncio.run(import_.on_program_text(FakeMessage(PROGRAM), state, None, USER))
    msg = FakeMessage("bench")
    asyncio.run(import_.on_search(msg, state, None, USER))
    assert rows(msg.sent[-1].kb)[0] == [
        ("Bench Press", ImportPick(exercise_id=1, left=1).pack())
    ]


def test_create_new_adds_exercise(wizard, monkeypatch):
    state, _ = wizard
    created = {}

    async def fake_add_exercise(session, name, user_id, muscle_names):
        created["args"] = (name, user_id, muscle_names)
        return ExerciseInfo(7, name)

    monkeypatch.setattr(import_, "add_exercise", fake_add_exercise)
    asyncio.run(import_.on_program_text(FakeMessage(PROGRAM), state, None, USER))
    asyncio.run(import_.cb_create(FakeCall(FakeMessage()), state))
    assert asyncio.run(state.get_state()) == ProgramImport.entering_muscles

    msg = FakeMessage("Hamstrings, Glutes")
    asyncio.run(import_.on_muscles(msg, state, None, USER))
    assert created["args"] == ("Romanian Deadlift", 42, ["Hamstrings", "Glutes"])
    assert asyncio.run(state.get_data())["matched"]["romanian deadlift"] == 7
    assert msg.sent[-1].text.startswith("Program: 2 days")


def test_replacing_label_when_program_exists(wizard):
    state, saved = wizard
    saved["existing"] = object()
    text = PROGRAM.replace("Romanian Deadlift", "RDL")
    msg = FakeMessage(text)
    asyncio.run(import_.on_program_text(msg, state, None, USER))
    assert rows(msg.sent[-1].kb) == rows(confirm_kb(replacing=True))


def test_cancel_clears_import(wizard):
    state, _ = wizard
    asyncio.run(import_.on_program_text(FakeMessage(PROGRAM), state, None, USER))
    call = FakeCall(FakeMessage())
    asyncio.run(import_.cb_cancel(call, state))
    assert call.message.sent[-1].text == "Import cancelled."
    assert asyncio.run(state.get_state()) is None

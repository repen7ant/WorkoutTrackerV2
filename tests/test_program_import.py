import asyncio
from decimal import Decimal

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import EditMessageReplyMarkup

from bot.catalog.api import ExerciseInfo, rank_similar
from bot.common.formatting import escape
from bot.handlers import start
from bot.programs.domain import InvalidProgram
from bot.programs.draft import decode_txt, plan_from_fsm, plan_to_fsm
from bot.programs.formatters import render_program
from bot.programs.handlers import import_, view
from bot.programs.keyboards import ImportPick, confirm_kb, match_kb
from bot.programs.parser import parse_program
from bot.programs.repository import StoredDay, StoredExercise, StoredProgram
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
    assert plan_from_fsm(stored).days[0].exercises[0].weeks[0][1].weight == Decimal(
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


NOT_MODIFIED = TelegramBadRequest(
    EditMessageReplyMarkup(), "Bad Request: message is not modified"
)


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
        self.documents: list[bytes] = []
        self.message_id = 100
        self.kb_removed = False

    async def answer(self, text, reply_markup=None, **kwargs):
        msg = SentMessage(200 + len(self.sent), text, reply_markup)
        self.sent.append(msg)
        return msg

    async def edit_text(self, text, reply_markup=None, **kwargs):
        self.sent.append(SentMessage(self.message_id, text, reply_markup))

    async def edit_reply_markup(self, reply_markup=None):
        if reply_markup is None and self.kb_removed:
            raise NOT_MODIFIED
        self.kb_removed = reply_markup is None

    async def answer_document(self, document, **kwargs):
        self.documents.append(document.data)


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
    assert summary.text == "Program: 1 week, 2 days — Push (2), Pull (2).\nSave it?"
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
    assert msg.sent[-1].text.startswith("Program: 1 week, 2 days")


def test_import_summary_with_weeks(wizard):
    state, _ = wizard
    text = (
        "# PROGRAM\n== Push ==\nBench Press: 100x5 / 102.5x5 / 105x5\n"
        "Plank: BWx1:00 / BWx1:15 / -\n== Pull ==\nRDL: 80x8 / 85x8 / 90x8\n"
    )
    msg = FakeMessage(text)
    asyncio.run(import_.on_program_text(msg, state, None, USER))
    assert (
        msg.sent[-1].text == "Program: 3 weeks, 2 days — Push (2), Pull (1).\nSave it?"
    )


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


# --- /program и /start ---


def test_start_explains_the_cycle():
    msg = FakeMessage("/start")
    asyncio.run(start.cmd_start(msg))
    text = msg.sent[-1].text
    for part in ("/workout", "/export", "# PROGRAM", "/program", "/settings"):
        assert part in text
    assert "week by week" in text
    assert "When the program ends" in text


@pytest.fixture
def stored(monkeypatch):
    calls = {"program": None, "deleted": 0}

    async def fake_get_program(session, user_id):
        return calls["program"]

    async def fake_delete(session, user_id):
        calls["deleted"] += 1
        return calls["deleted"] == 1

    monkeypatch.setattr(view, "get_program", fake_get_program)
    monkeypatch.setattr(view, "delete_program", fake_delete)
    return calls


def _stored_program(text=PROGRAM):
    plan = parse_program(text)
    days = [
        StoredDay(
            i,
            day.name,
            [
                StoredExercise(1, ex.name, ex.notes, [list(w) for w in ex.weeks])
                for ex in day.exercises
            ],
        )
        for i, day in enumerate(plan.days, start=1)
    ]
    return StoredProgram(id=1, weeks=plan.weeks, days=days, done={})


def test_program_without_program_explains_import(stored):
    msg = FakeMessage("/program")
    asyncio.run(view.cmd_program(msg, None, USER))
    assert "# PROGRAM" in msg.sent[-1].text
    assert msg.sent[-1].kb is None


def test_program_shows_it_in_import_format(stored):
    stored["program"] = _stored_program(PROGRAM.replace("pause", "pause <3s>"))
    msg = FakeMessage("/program")
    asyncio.run(view.cmd_program(msg, None, USER))
    sent = msg.sent[-1]
    assert sent.text == (
        "Week 1 of 1 · 0 of 2 sessions done\n<pre>"
        + escape(render_program(stored["program"].days))
        + "</pre>"
    )
    assert rows(sent.kb) == [[("Delete program", "pg_delete")]]


def test_long_program_is_sent_as_file(stored):
    days = "".join(
        f"== Day {d} ==\n"
        + "".join(
            f"Exercise {d}-{e} with a long name: " + ", ".join(["100x5"] * 10) + "\n"
            for e in range(12)
        )
        for d in range(10)
    )
    stored["program"] = _stored_program("# PROGRAM\n" + days)
    msg = FakeMessage("/program")
    asyncio.run(view.cmd_program(msg, None, USER))
    assert msg.documents[-1].startswith(b"# PROGRAM\n")
    assert msg.sent == []


def test_delete_asks_then_deletes_once(stored):
    stored["program"] = _stored_program()
    ask = FakeCall(FakeMessage())
    asyncio.run(view.cb_delete(ask))
    question = ask.message.sent[-1]
    assert question.text.startswith("Delete program?")
    assert rows(question.kb) == [[("Yes", "pg_delete_yes"), ("No", "pg_delete_no")]]

    yes = FakeCall(FakeMessage())
    asyncio.run(view.cb_delete_yes(yes, None, USER))
    assert yes.message.sent[-1].text == "Program deleted."
    # второй тап: кнопок уже нет
    yes.message.kb_removed = True
    asyncio.run(view.cb_delete_yes(yes, None, USER))
    assert stored["deleted"] == 1


@pytest.mark.parametrize(
    ("text", "matches"),
    [
        ("```\n# PROGRAM\n== A ==\nDips: BWx5\n```", True),
        ("# program\n== A ==\nDips: BWx5", True),
        ("hello", False),
    ],
)
def test_program_message_filter(text, matches):
    from datetime import UTC, datetime

    from aiogram.types import Chat, Message

    message = Message(
        message_id=1, date=datetime.now(UTC), chat=Chat(id=1, type="private"), text=text
    )
    assert bool(import_.IS_PROGRAM.resolve(message)) is matches

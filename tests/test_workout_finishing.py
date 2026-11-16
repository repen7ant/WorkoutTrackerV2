import asyncio
from datetime import UTC, datetime

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import EditMessageText

from bot.users.models import User
from bot.utils import fsm_json
from bot.workouts.formatters import format_confirm, format_workout_main
from bot.workouts.handlers import finishing
from bot.workouts.handlers.common import PROGRAM_FINISHED
from bot.workouts.handlers.finishing import Step, step_after_date, step_after_finish
from bot.workouts.keyboards import (
    cancel_confirm_kb,
    confirm_save_kb,
    finish_date_kb,
    finish_notes_kb,
    workout_main_kb,
)
from bot.workouts.states import WorkoutSession

NOT_MODIFIED = TelegramBadRequest(
    EditMessageText(text=""), "Bad Request: message is not modified"
)
DRAFT = {
    "exercises": [
        {
            "exercise_id": 7,
            "exercise_name": "Bench Press",
            "notes": None,
            "sets": [{"weight": None, "reps": 5, "seconds": None}],
        }
    ],
    "workout_date": "2026-11-09",
    "notes": "week 3",
}


def rows(kb):
    if kb is None:
        return None
    return [[(b.text, b.callback_data) for b in row] for row in kb.inline_keyboard]


class FakeMessage:
    """Сообщение бота. Как и Telegram, отказывает в правке, которая ничего
    не меняет, — так приходит второе нажатие той же кнопки."""

    def __init__(self, text, kb):
        self.text, self.kb = text, rows(kb)
        self.answers = []

    async def answer(self, text, **kwargs):
        self.answers.append(text)

    async def edit_text(self, text, parse_mode=None, reply_markup=None):
        self._edit(text, rows(reply_markup))

    async def edit_reply_markup(self, reply_markup=None):
        self._edit(self.text, rows(reply_markup))

    def _edit(self, text, kb):
        if (text, kb) == (self.text, self.kb):
            raise NOT_MODIFIED
        self.text, self.kb = text, kb


class FakeCall:
    def __init__(self, message):
        self.message, self.answered = message, False

    async def answer(self, text=None, show_alert=False):
        self.answered = True


class RedisLikeStorage(MemoryStorage):
    """Данные проходят через fsm_json, как в RedisStorage: то, что Redis
    не сохранит, падает сразу, а не только на сервере."""

    async def set_data(self, key, data):
        await super().set_data(key, fsm_json.loads(fsm_json.dumps(data)))


def make_state(step) -> FSMContext:
    state = FSMContext(
        storage=RedisLikeStorage(), key=StorageKey(bot_id=1, chat_id=1, user_id=1)
    )

    async def fill():
        await state.set_state(step)
        await state.set_data(DRAFT)

    asyncio.run(fill())
    return state


@pytest.mark.parametrize(
    ("ask_date", "ask_notes", "expected"),
    [
        (True, True, Step.DATE),
        (True, False, Step.DATE),
        (False, True, Step.NOTES),
        (False, False, Step.YES_NO),
    ],
)
def test_step_after_finish(ask_date, ask_notes, expected):
    assert step_after_finish(ask_date, ask_notes) is expected


@pytest.mark.parametrize(
    ("ask_notes", "typed", "expected"),
    [
        (True, False, Step.NOTES),
        (True, True, Step.NOTES),
        (False, False, Step.SAVE),
        (False, True, Step.CONFIRM),
    ],
)
def test_step_after_date(ask_notes, typed, expected):
    assert step_after_date(ask_notes, typed) is expected


def test_cancel_asks_the_question_in_text():
    """Иначе на экране подтверждения Yes стоял бы под «Save workout?»."""
    msg = FakeMessage(format_confirm(DRAFT), confirm_save_kb())
    state = make_state(WorkoutSession.confirming)
    asyncio.run(finishing.cb_cancel(FakeCall(msg), state))
    assert (msg.text, msg.kb) == ("Cancel workout?", rows(cancel_confirm_kb()))


@pytest.mark.parametrize(
    ("step", "text", "kb"),
    [
        (
            WorkoutSession.active,
            format_workout_main(DRAFT["exercises"]),
            workout_main_kb(),
        ),
        (WorkoutSession.finishing, "Choose workout date:", finish_date_kb()),
        (WorkoutSession.entering_notes, "Add notes or skip:", finish_notes_kb()),
        (WorkoutSession.confirming, format_confirm(DRAFT), confirm_save_kb()),
    ],
)
def test_no_restores_the_step(step, text, kb):
    msg = FakeMessage("Cancel workout?", cancel_confirm_kb())
    asyncio.run(finishing.cb_cancel_abort(FakeCall(msg), make_state(step)))
    assert (msg.text, msg.kb) == (text, rows(kb))


def test_double_tap_on_no_is_silent():
    # первое нажатие уже вернуло шаг
    msg = FakeMessage("Choose workout date:", finish_date_kb())
    call = FakeCall(msg)
    asyncio.run(finishing.cb_cancel_abort(call, make_state(WorkoutSession.finishing)))
    assert call.answered


def test_losing_tap_of_double_save_is_silent():
    # первое нажатие уже сняло кнопки и сохраняет тренировку
    msg = FakeMessage(format_workout_main(DRAFT["exercises"]), None)
    call = FakeCall(msg)
    user = User(
        id=1,
        ask_workout_date=False,
        ask_workout_notes=False,
        exercise_log_size=10,
        utc_offset=180,
    )
    state = make_state(WorkoutSession.active)
    asyncio.run(finishing.cb_finish_confirm(call, state, None, user))
    assert call.answered


def test_yes_dates_the_workout_by_finish():
    """Yes нажали позже — дата всё равно день нажатия Finish session."""
    msg = FakeMessage(format_workout_main(DRAFT["exercises"]), None)
    state = make_state(WorkoutSession.active)
    asyncio.run(state.update_data(finished_at="2026-01-05T20:59:30+00:00"))
    user = User(
        id=1,
        ask_workout_date=False,
        ask_workout_notes=False,
        exercise_log_size=10,
        utc_offset=180,
    )
    asyncio.run(finishing.cb_finish_confirm(FakeCall(msg), state, None, user))
    assert asyncio.run(state.get_data())["workout_date"] == "2026-01-05"


def test_save_message_shows_workout_time(monkeypatch):
    async def fake_record_workout(session, record, program_day=None, program_week=None):
        return 1

    monkeypatch.setattr(finishing, "record_workout", fake_record_workout)
    msg = FakeMessage(format_confirm(DRAFT), confirm_save_kb())
    state = make_state(WorkoutSession.confirming)
    asyncio.run(
        state.update_data(
            started_at="2026-11-09T15:05:40+00:00",
            finished_at="2026-11-09T16:20:10+00:00",
        )
    )
    user = User(
        id=1,
        ask_workout_date=True,
        ask_workout_notes=True,
        exercise_log_size=10,
        utc_offset=180,
    )
    asyncio.run(finishing.cb_save(FakeCall(msg), state, None, user))
    assert msg.answers == ["Workout saved: 09-11-26 · 18:05–19:20 (1 h 15 min)."]


def test_state_is_stored_like_redis():
    """Положить в FSM то, что Redis не сохранит, нельзя и в тестах."""
    state = make_state(WorkoutSession.active)
    with pytest.raises(TypeError):
        asyncio.run(state.update_data(started_at=datetime.now(UTC)))


def test_finish_records_end_time():
    msg = FakeMessage(format_workout_main(DRAFT["exercises"]), workout_main_kb())
    user = User(
        id=1,
        ask_workout_date=False,
        ask_workout_notes=False,
        exercise_log_size=10,
        utc_offset=180,
    )
    state = make_state(WorkoutSession.active)
    asyncio.run(finishing.cb_finish(FakeCall(msg), state, user))
    finished_at = asyncio.run(state.get_data())["finished_at"]
    assert datetime.fromisoformat(finished_at).tzinfo is not None


PROGRAM_DRAFT = {
    **DRAFT,
    "program_id": 7,
    "program_day": "Pull",
    "program_day_position": 2,
    "program_week": 3,
}
SAVING_USER = User(
    id=1,
    ask_workout_date=True,
    ask_workout_notes=True,
    exercise_log_size=10,
    utc_offset=180,
)


def _save_program_workout(
    monkeypatch, draft, record_error=None, complete_error=None, completed=None
):
    calls = {"recorded": None, "completed": []}

    async def fake_record_workout(session, record, program_day=None, program_week=None):
        if record_error is not None:
            raise record_error
        calls["recorded"] = (program_day, program_week)
        return 1

    async def fake_complete_session(session, user_id, program_id, week, day_position):
        if complete_error is not None:
            raise complete_error
        calls["completed"].append((user_id, program_id, week, day_position))
        return completed

    monkeypatch.setattr(finishing, "record_workout", fake_record_workout)
    monkeypatch.setattr(finishing, "complete_session", fake_complete_session)
    msg = FakeMessage(format_confirm(draft), confirm_save_kb())
    state = make_state(WorkoutSession.confirming)
    asyncio.run(state.set_data(draft))
    asyncio.run(finishing.cb_save(FakeCall(msg), state, None, SAVING_USER))
    return calls, msg, state


def test_save_completes_session(monkeypatch):
    calls, msg, state = _save_program_workout(monkeypatch, PROGRAM_DRAFT)
    assert calls == {"recorded": ("Pull", 3), "completed": [(1, 7, 3, 2)]}
    assert msg.answers[-1].startswith("Workout saved")
    assert asyncio.run(state.get_state()) is None


def test_save_failure_does_not_complete_session(monkeypatch):
    from bot.workouts.domain import InvalidWorkout

    calls, _, state = _save_program_workout(
        monkeypatch, PROGRAM_DRAFT, record_error=InvalidWorkout("bad")
    )
    assert calls["completed"] == []
    assert asyncio.run(state.get_state()) == WorkoutSession.confirming


def test_free_workout_does_not_complete_session(monkeypatch):
    calls, _, _ = _save_program_workout(monkeypatch, DRAFT)
    assert calls == {"recorded": (None, None), "completed": []}


def test_session_error_keeps_saved_workout(monkeypatch):
    """Тренировка уже сохранена: «try again» сохранило бы её второй раз."""
    from sqlalchemy.exc import OperationalError

    calls, msg, state = _save_program_workout(
        monkeypatch,
        PROGRAM_DRAFT,
        complete_error=OperationalError("INSERT", {}, Exception("db down")),
    )
    assert calls["recorded"] == ("Pull", 3)
    assert msg.answers[-1].startswith("Workout saved")
    assert asyncio.run(state.get_state()) is None


def _program_done(finished: bool):
    from bot.programs.repository import StoredDay, StoredExercise, StoredProgram
    from bot.workouts.domain import SetEntry

    day = StoredDay(1, "Pull", [StoredExercise(5, "Row", None, [[SetEntry(None, 8)]])])
    return StoredProgram(
        id=7, weeks=1, days=[day], done={(1, 1): False} if finished else {}
    )


@pytest.mark.parametrize(
    ("completed", "finished"),
    [
        (_program_done(finished=True), True),
        (_program_done(finished=False), False),
        (None, False),  # программу заменили, пока шла тренировка
    ],
)
def test_save_says_when_program_is_finished(monkeypatch, completed, finished):
    _, msg, _ = _save_program_workout(monkeypatch, PROGRAM_DRAFT, completed=completed)
    assert msg.answers[0].startswith("Workout saved")
    assert (PROGRAM_FINISHED in msg.answers) is finished

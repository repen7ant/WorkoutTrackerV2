import asyncio

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import EditMessageText

from bot.users.models import User
from bot.workouts.formatters import format_confirm, format_workout_main
from bot.workouts.handlers import finishing
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


def make_state(step) -> FSMContext:
    state = FSMContext(
        storage=MemoryStorage(), key=StorageKey(bot_id=1, chat_id=1, user_id=1)
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
        id=1, ask_workout_date=False, ask_workout_notes=False, exercise_log_size=10
    )
    state = make_state(WorkoutSession.active)
    asyncio.run(finishing.cb_finish_confirm(call, state, None, user))
    assert call.answered

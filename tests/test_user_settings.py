import asyncio
from datetime import UTC, datetime

import pytest

from bot.users.handlers import SETTINGS_TEXT, cb_settings_change
from bot.users.keyboards import SettingsChange, settings_kb, timezone_kb
from bot.users.models import User
from bot.users.service import update_setting
from bot.users.settings import (
    LOG_SIZES,
    Setting,
    format_utc_offset,
    next_log_size,
    to_local,
)


class FakeSession:
    committed = False

    async def commit(self):
        self.committed = True


class FakeMessage:
    def __init__(self, text):
        self.text, self.kb = text, None

    async def edit_text(self, text, parse_mode=None, reply_markup=None):
        self.text, self.kb = text, reply_markup


class FakeCall:
    def __init__(self, message):
        self.message, self.toast = message, None

    async def answer(self, text=None, show_alert=False):
        self.toast = text


def make_user(**values) -> User:
    defaults = {
        "ask_workout_date": True,
        "ask_workout_notes": True,
        "exercise_log_size": 10,
        "utc_offset": 180,
    }
    return User(id=1, **(defaults | values))


def buttons(kb):
    return [[(b.text, b.callback_data) for b in row] for row in kb.inline_keyboard]


def change(setting, value):
    return SettingsChange(setting=setting, value=value).pack()


def test_log_size_cycles():
    assert [next_log_size(size) for size in LOG_SIZES] == [5, 3, 0, 10]


def test_unknown_log_size_falls_back_to_default():
    assert next_log_size(7) == 10


def test_settings_kb_defaults():
    assert buttons(settings_kb(make_user())) == [
        [("Workout date: ask", change(Setting.DATE, 0))],
        [("Workout notes: ask", change(Setting.NOTES, 0))],
        [("Exercise log: 10 workouts", change(Setting.LOG, 5))],
        [("Time zone: UTC+3", "settings_tz")],
    ]


def test_settings_kb_changed():
    user = make_user(
        ask_workout_date=False,
        ask_workout_notes=False,
        exercise_log_size=0,
        utc_offset=330,
    )
    assert buttons(settings_kb(user)) == [
        [("Workout date: today", change(Setting.DATE, 1))],
        [("Workout notes: off", change(Setting.NOTES, 1))],
        [("Exercise log: off", change(Setting.LOG, 10))],
        [("Time zone: UTC+5:30", "settings_tz")],
    ]


def test_log_size_buttons():
    log_buttons = [
        buttons(settings_kb(make_user(exercise_log_size=size)))[2][0] for size in (5, 3)
    ]
    assert log_buttons == [
        ("Exercise log: 5 workouts", change(Setting.LOG, 3)),
        ("Exercise log: 3 workouts", change(Setting.LOG, 0)),
    ]


def test_update_setting_saves_value():
    user, session = make_user(), FakeSession()
    asyncio.run(update_setting(session, user, Setting.NOTES, 0))
    assert user.ask_workout_notes is False
    assert session.committed


def test_same_value_twice_does_not_flip_back():
    """Двойное нажатие или кнопка старого сообщения /settings."""
    user, session = make_user(), FakeSession()
    for _ in range(2):
        asyncio.run(update_setting(session, user, Setting.DATE, 0))
    assert user.ask_workout_date is False


def test_update_setting_ignores_unknown_log_size():
    user, session = make_user(), FakeSession()
    asyncio.run(update_setting(session, user, Setting.LOG, 7))
    assert user.exercise_log_size == 10
    assert not session.committed


@pytest.mark.parametrize(
    ("offset", "expected"),
    [
        (180, datetime(2026, 11, 10, 1, 30)),  # в Москве уже завтра
        (-600, datetime(2026, 11, 9, 12, 30)),
        (330, datetime(2026, 11, 10, 4, 0)),
    ],
)
def test_to_local(offset, expected):
    moment = datetime(2026, 11, 9, 22, 30, tzinfo=UTC)
    assert to_local(moment, offset).replace(tzinfo=None) == expected


@pytest.mark.parametrize(
    ("minutes", "text"),
    [
        (180, "UTC+3"),
        (330, "UTC+5:30"),
        (345, "UTC+5:45"),
        (-210, "UTC-3:30"),
        (-600, "UTC-10"),
        (0, "UTC+0"),
    ],
)
def test_format_utc_offset(minutes, text):
    assert format_utc_offset(minutes) == text


def test_timezone_kb():
    rows = buttons(timezone_kb(datetime(2026, 11, 9, 15, 5, tzinfo=UTC)))
    assert rows[-1] == [("Back", "settings_back")]
    times = [button for row in rows[:-1] for button in row]
    labels = [text for text, _ in times]
    assert len(times) == 31
    assert labels == sorted(set(labels))  # по времени суток, без повторов
    assert all(len(row) == 4 for row in rows[:-2])
    assert ("18:05", change(Setting.TIMEZONE, 180)) in times
    assert ("20:35", change(Setting.TIMEZONE, 330)) in times
    assert ("05:05", change(Setting.TIMEZONE, -600)) in times


def test_timezone_saved():
    user, session = make_user(), FakeSession()
    asyncio.run(update_setting(session, user, Setting.TIMEZONE, 330))
    assert (user.utc_offset, session.committed) == (330, True)


def test_unknown_timezone_ignored():
    user, session = make_user(), FakeSession()
    asyncio.run(update_setting(session, user, Setting.TIMEZONE, 200))
    assert (user.utc_offset, session.committed) == (180, False)


def test_choosing_time_returns_to_settings():
    user = make_user()
    call = FakeCall(FakeMessage("What time is it for you now?"))
    data = SettingsChange(setting=Setting.TIMEZONE, value=330)
    asyncio.run(cb_settings_change(call, data, FakeSession(), user))
    assert call.message.text == SETTINGS_TEXT
    assert buttons(call.message.kb) == buttons(settings_kb(user))
    assert call.toast.startswith("Saved. Your time: ")

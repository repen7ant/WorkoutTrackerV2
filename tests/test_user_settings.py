import asyncio

from bot.users.keyboards import SettingsChange, settings_kb
from bot.users.models import User
from bot.users.service import update_setting
from bot.users.settings import LOG_SIZES, Setting, next_log_size


class FakeSession:
    committed = False

    async def commit(self):
        self.committed = True


def make_user(**values) -> User:
    defaults = {
        "ask_workout_date": True,
        "ask_workout_notes": True,
        "exercise_log_size": 10,
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
    ]


def test_settings_kb_changed():
    user = make_user(
        ask_workout_date=False, ask_workout_notes=False, exercise_log_size=0
    )
    assert buttons(settings_kb(user)) == [
        [("Workout date: today", change(Setting.DATE, 1))],
        [("Workout notes: off", change(Setting.NOTES, 1))],
        [("Exercise log: off", change(Setting.LOG, 10))],
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

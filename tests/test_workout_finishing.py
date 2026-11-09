import pytest

from bot.workouts.handlers.finishing import Step, step_after_date, step_after_finish


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

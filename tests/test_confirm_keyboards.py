import pytest

from bot.catalog.keyboards import ExerciseDeleteConfirm, delete_confirm_kb
from bot.workouts.keyboards import cancel_confirm_kb, finish_confirm_kb


@pytest.mark.parametrize(
    ("kb", "yes", "no"),
    [
        (finish_confirm_kb(), "wk_finish_confirm", "wk_cancel_abort"),
        (cancel_confirm_kb(), "wk_cancel_confirm", "wk_cancel_abort"),
        (
            delete_confirm_kb(7),
            ExerciseDeleteConfirm(exercise_id=7).pack(),
            "ex_delete_cancel",
        ),
    ],
)
def test_confirmations_are_plain_yes_no(kb, yes, no):
    rows = [[(b.text, b.callback_data) for b in row] for row in kb.inline_keyboard]
    assert rows == [[("Yes", yes), ("No", no)]]

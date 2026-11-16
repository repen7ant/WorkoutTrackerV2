"""Разбор подхода из текста: '100x5', 'BWx10', 'BWx1:30', '20x45s'."""

import re
from decimal import Decimal, InvalidOperation

from bot.workouts.domain import SetEntry

# после upper(): «1:30» — минуты:секунды, «45S» — секунды
_MIN_SEC = re.compile(r"(\d+):([0-5]\d)")
_SEC = re.compile(r"(\d+)S")
# после upper(): русские «Х» и «С» (секунды) вместо X и S, запятая в весе —
# с телефона так пишут часто
_SET_TYPOS = str.maketrans({"\u0425": "X", "\u0421": "S", ",": "."})
# буквы формата подхода после upper(): X и русская Х, BW, S и русская С у секунд
_SET_LETTERS = frozenset("XBWS\u0425\u0421")


def is_note(text: str | None) -> bool:
    """
    Заметка — текст со словами. Текст без них — попытка ввести подход, даже
    с опечаткой («100 5», «100x»): на него нужна подсказка формата, а не заметка.
    """
    return bool(text) and any(
        ch.isalpha() and ch not in _SET_LETTERS for ch in text.upper()
    )


def _parse_seconds(text: str) -> int | None:
    if m := _MIN_SEC.fullmatch(text):
        return int(m[1]) * 60 + int(m[2])
    if m := _SEC.fullmatch(text):
        return int(m[1])
    return None


def parse_set(text: str | None) -> SetEntry | None:
    """Разбирает '100x5', 'BWx10' или время: 'BWx1:30', '20x45s'.
    Допустимость значений решает SetEntry."""
    # в состоянии ввода подходов может прилететь стикер или фото — там text is None
    if not text:
        return None
    parts = text.strip().upper().translate(_SET_TYPOS).split("X")
    if len(parts) != 2:
        return None
    weight_str, amount_str = parts
    try:
        weight = None if weight_str == "BW" else Decimal(weight_str)
        seconds = _parse_seconds(amount_str)
        if seconds is not None:
            return SetEntry.create(weight, seconds=seconds)
        return SetEntry.create(weight, reps=int(amount_str))
    except (ValueError, InvalidOperation):
        # InvalidWorkout — тоже ValueError
        return None

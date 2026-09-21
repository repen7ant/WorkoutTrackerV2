"""
Сериализация данных FSM для RedisStorage.

Вес подхода — Decimal, а json его не умеет, поэтому дефолтный RedisStorage
падает на первом же подходе с весом. Тег сохраняет тип в обе стороны: без него
вес вернулся бы из Redis строкой и ушёл бы в Numeric-колонку строкой.

MemoryStorage кладёт объекты как есть и такой обёртки не требует — поэтому на
нём проблема не видна, и проверять хендлеры надо именно на Redis.
"""

import json
from decimal import Decimal
from typing import Any

_TAG = "__decimal__"


def _default(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return {_TAG: str(obj)}
    msg = f"Object of type {type(obj).__name__} is not JSON serializable"
    raise TypeError(msg)


def _object_hook(obj: dict[str, Any]) -> Any:
    if len(obj) == 1 and _TAG in obj:
        return Decimal(obj[_TAG])
    return obj


def dumps(obj: Any) -> str:
    return json.dumps(obj, default=_default)


def loads(value: str | bytes) -> Any:
    return json.loads(value, object_hook=_object_hook)

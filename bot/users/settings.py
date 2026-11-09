from datetime import UTC, datetime, timedelta, timezone
from enum import StrEnum

# порядок переключения в /settings; 0 — лог не показывать
LOG_SIZES = (10, 5, 3, 0)
# минуты от UTC. Целые часы — от −10 до +13: по одному на каждый час суток,
# поэтому время на кнопках выбора пояса не повторяется
UTC_OFFSETS = (*range(-600, 781, 60), -210, 210, 270, 330, 345, 390, 570)


class Setting(StrEnum):
    DATE = "date"
    NOTES = "notes"
    LOG = "log"
    TIMEZONE = "tz"


def next_log_size(size: int) -> int:
    if size not in LOG_SIZES:
        return LOG_SIZES[0]
    return LOG_SIZES[(LOG_SIZES.index(size) + 1) % len(LOG_SIZES)]


def to_local(moment: datetime, utc_offset: int) -> datetime:
    return moment.astimezone(timezone(timedelta(minutes=utc_offset)))


def local_now(utc_offset: int) -> datetime:
    return to_local(datetime.now(UTC), utc_offset)


def format_utc_offset(minutes: int) -> str:
    sign = "-" if minutes < 0 else "+"
    hours, mins = divmod(abs(minutes), 60)
    return f"UTC{sign}{hours}" + (f":{mins:02d}" if mins else "")

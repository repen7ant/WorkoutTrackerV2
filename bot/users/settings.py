# порядок переключения в /settings; 0 — лог не показывать
LOG_SIZES = (10, 5, 3, 0)


def next_log_size(size: int) -> int:
    if size not in LOG_SIZES:
        return LOG_SIZES[0]
    return LOG_SIZES[(LOG_SIZES.index(size) + 1) % len(LOG_SIZES)]

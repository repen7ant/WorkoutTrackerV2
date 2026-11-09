from bot.users.settings import LOG_SIZES, next_log_size


def test_log_size_cycles():
    assert [next_log_size(size) for size in LOG_SIZES] == [5, 3, 0, 10]


def test_unknown_log_size_falls_back_to_default():
    assert next_log_size(7) == 10

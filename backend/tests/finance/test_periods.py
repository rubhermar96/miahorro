import datetime as dt

import pytest
from hypothesis import given
from hypothesis import strategies as st

from finance.periods import last_periods, period_of, shift


@pytest.mark.parametrize(
    ("date", "start_day", "expected"),
    [
        (dt.date(2026, 10, 19), 1, (dt.date(2026, 10, 1), dt.date(2026, 10, 31))),
        (dt.date(2026, 10, 19), 25, (dt.date(2026, 9, 25), dt.date(2026, 10, 24))),
        (dt.date(2026, 10, 25), 25, (dt.date(2026, 10, 25), dt.date(2026, 11, 24))),
        (dt.date(2027, 1, 5), 25, (dt.date(2026, 12, 25), dt.date(2027, 1, 24))),
        (dt.date(2026, 2, 28), 28, (dt.date(2026, 2, 28), dt.date(2026, 3, 27))),
    ],
)
def test_period_of(date: dt.date, start_day: int, expected: tuple[dt.date, dt.date]) -> None:
    assert period_of(date, start_day) == expected


@given(
    date=st.dates(min_value=dt.date(2000, 1, 1), max_value=dt.date(2100, 1, 1)),
    start_day=st.integers(min_value=1, max_value=28),
)
def test_periods_tile_the_calendar(date: dt.date, start_day: int) -> None:
    start, end = period_of(date, start_day)

    assert start <= date <= end
    assert start.day == start_day
    assert period_of(end + dt.timedelta(days=1), start_day)[0] == shift(start, 1, start_day)


def test_last_periods_end_today() -> None:
    assert last_periods(dt.date(2026, 10, 19), 25, 2) == [
        (dt.date(2026, 8, 25), dt.date(2026, 9, 24)),
        (dt.date(2026, 9, 25), dt.date(2026, 10, 19)),
    ]

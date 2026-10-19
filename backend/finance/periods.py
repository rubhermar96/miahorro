"""Financial months (RF-USR-04): each one starts on the user's chosen day (usually payday),
from 1 to 28 so every month has it."""

import datetime as dt


def _start(year: int, month: int, day: int) -> dt.date:
    """The `day` of a month counted from year/month, wrapping months over 12."""
    return dt.date(year + (month - 1) // 12, (month - 1) % 12 + 1, day)


def period_of(date: dt.date, start_day: int) -> tuple[dt.date, dt.date]:
    """The financial month that contains `date`: first and last day."""
    start = (
        _start(date.year, date.month, start_day)
        if date.day >= start_day
        else _start(date.year, date.month - 1, start_day)
    )
    return start, shift(start, 1, start_day) - dt.timedelta(days=1)


def shift(start: dt.date, months: int, start_day: int) -> dt.date:
    """The first day of the financial month `months` before (negative) or after `start`."""
    return _start(start.year, start.month + months, start_day)


def last_periods(today: dt.date, start_day: int, count: int) -> list[tuple[dt.date, dt.date]]:
    """The last `count` financial months, oldest first; the current one ends today."""
    current, _ = period_of(today, start_day)
    periods = []
    for back in range(count - 1, -1, -1):
        start = shift(current, -back, start_day)
        end = shift(start, 1, start_day) - dt.timedelta(days=1)
        periods.append((start, min(end, today)))
    return periods

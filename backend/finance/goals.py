"""Savings goal arithmetic (RF-OBJ-02): how much a month is needed and when the goal is
reached at the current pace. Pure functions on exact decimals."""

import datetime as dt
from decimal import ROUND_CEILING, Decimal

from finance.money import CENT, round_cents

# Average month length in days (365.25 / 12), to turn days into months.
_DAYS_PER_MONTH = Decimal("30.4375")


def months_left(today: dt.date, target: dt.date) -> int:
    """Monthly contributions still possible before the target date, counting this month.

    15/10 → 31/12 is 3 (October, November, December); a date already past leaves 1, the
    contribution still to make now."""
    months = (target.year - today.year) * 12 + target.month - today.month + 1
    if target.day < today.day:
        months -= 1  # this month's day has already gone in the target month
    return max(months, 1)


def required_monthly(remaining: Decimal, today: dt.date, target: dt.date) -> Decimal:
    """What to put aside each month to reach the target on time (rounded up to the cent)."""
    if remaining <= 0:
        return Decimal("0.00")
    per_month = remaining / months_left(today, target)
    return per_month.quantize(CENT, rounding=ROUND_CEILING)


def months_between(start: dt.date, end: dt.date) -> Decimal:
    return Decimal((end - start).days) / _DAYS_PER_MONTH


def monthly_pace(change: Decimal, start: dt.date, end: dt.date) -> Decimal | None:
    """Average saved per month between two dates; None if the period is under a month."""
    months = months_between(start, end)
    if months < 1:
        return None
    return round_cents(change / months)


def estimated_date(remaining: Decimal, pace: Decimal | None, today: dt.date) -> dt.date | None:
    """When the goal is reached at this pace; None if it is not growing."""
    if remaining <= 0:
        return today
    if pace is None or pace <= 0:
        return None
    days = int((remaining / pace * _DAYS_PER_MONTH).to_integral_value(rounding=ROUND_CEILING))
    if days > 365 * 100:
        return None  # a century away is "not at this pace"
    return today + dt.timedelta(days=days)

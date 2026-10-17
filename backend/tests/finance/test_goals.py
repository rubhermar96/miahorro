import datetime as dt
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from finance.goals import estimated_date, monthly_pace, months_left, required_monthly

TODAY = dt.date(2026, 10, 15)


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        (dt.date(2026, 12, 31), 3),  # October, November, December
        (dt.date(2026, 12, 10), 2),  # in December the 15th never comes before the 10th
        (dt.date(2026, 10, 20), 1),
        (dt.date(2026, 9, 1), 1),  # past: what is missing, now
        (dt.date(2029, 10, 15), 37),
    ],
)
def test_months_left(target: dt.date, expected: int) -> None:
    assert months_left(TODAY, target) == expected


def test_required_monthly_rounds_up_to_the_cent() -> None:
    assert required_monthly(Decimal("1000"), TODAY, dt.date(2026, 12, 31)) == Decimal("333.34")
    assert required_monthly(Decimal("0"), TODAY, dt.date(2026, 12, 31)) == Decimal("0.00")
    assert required_monthly(Decimal("-5"), TODAY, dt.date(2026, 12, 31)) == Decimal("0.00")


@given(
    remaining=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("1e7"), places=2),
    days=st.integers(min_value=0, max_value=365 * 30),
)
def test_paying_the_required_amount_every_month_reaches_the_goal(
    remaining: Decimal, days: int
) -> None:
    target = TODAY + dt.timedelta(days=days)
    monthly = required_monthly(remaining, TODAY, target)

    assert monthly * months_left(TODAY, target) >= remaining


def test_pace_needs_at_least_a_month() -> None:
    assert monthly_pace(Decimal("900"), TODAY - dt.timedelta(days=91), TODAY) == Decimal("301.03")
    assert monthly_pace(Decimal("900"), TODAY - dt.timedelta(days=20), TODAY) is None


def test_estimated_date_at_the_current_pace() -> None:
    assert estimated_date(Decimal("600"), Decimal("300"), TODAY) == dt.date(2026, 12, 15)
    assert estimated_date(Decimal("0"), Decimal("300"), TODAY) == TODAY
    assert estimated_date(Decimal("600"), Decimal("0"), TODAY) is None
    assert estimated_date(Decimal("600"), None, TODAY) is None
    assert estimated_date(Decimal("1e9"), Decimal("1"), TODAY) is None  # not in this life

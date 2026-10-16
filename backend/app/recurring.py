"""Recurring income and expenses (RF-MOV-06): forecast and fulfilment.

An item expects a movement around its next date. When one arrives in its account with the
text in the concept, the right sign and an amount within the tolerance, the item counts as
done for that date and moves to the next one.
"""

import calendar
import datetime as dt
from collections.abc import Iterable
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.capture import RecurringItem
from app.models.transactions import Transaction
from app.models.user import User
from app.ownership import owned
from importers.values import plain

# How far from the expected date a movement still counts (banks move dates around weekends).
EARLY = dt.timedelta(days=7)
LATE = dt.timedelta(days=10)
_MONTHS = {"monthly": 1, "quarterly": 3, "semiannual": 6, "yearly": 12}


def advance(date: dt.date, frequency: str) -> dt.date:
    """The next date: same day of the month (or the last one if the month is shorter)."""
    if frequency == "weekly":
        return date + dt.timedelta(days=7)
    months = date.month - 1 + _MONTHS[frequency]
    year, month = date.year + months // 12, months % 12 + 1
    return date.replace(
        year=year, month=month, day=min(date.day, calendar.monthrange(year, month)[1])
    )


def occurrences(item: RecurringItem, until: dt.date) -> list[dt.date]:
    dates: list[dt.date] = []
    date = item.next_date
    while date <= until and len(dates) < 60:
        dates.append(date)
        date = advance(date, item.frequency)
    return dates


def _fits(item: RecurringItem, row: Transaction) -> bool:
    if row.account_id != item.account_id or row.kind != item.kind:
        return False
    if " ".join(plain(item.match_text).split()) not in " ".join(plain(row.description).split()):
        return False
    margin = item.amount * item.tolerance / Decimal(100)
    return abs(abs(row.amount) - item.amount) <= margin and (
        item.next_date - EARLY <= row.date <= item.next_date + LATE
    )


def fulfil(db: Session, user: User, rows: Iterable[Transaction]) -> int:
    """Mark the items that these new movements fulfil; returns how many."""
    candidates = [row for row in rows if row.kind in ("expense", "income")]
    if not candidates:
        return 0
    done = 0
    for item in db.scalars(owned(RecurringItem, user)):
        for row in sorted(candidates, key=lambda r: r.date):
            if _fits(item, row):
                item.last_transaction_id = row.id
                item.next_date = advance(item.next_date, item.frequency)
                done += 1
    return done

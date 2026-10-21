"""Reports (RF-INF-03, RF-INF-04): income against expenses over any stretch of time, and where
the money goes by category, merchant or tag, next to earlier periods."""

import datetime as dt
from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from app.goals import Period
from app.models.transactions import Category, Transaction
from app.models.user import User
from app.ownership import owned
from app.rules import suggest_match_text
from finance.periods import period_of, shift

type Grouping = Literal["month", "year", "total"]
type SpendingBy = Literal["category", "merchant", "tag"]

_ZERO = Decimal(0)
_DAY = dt.timedelta(days=1)


# --- Income and expenses ----------------------------------------------------------------------


def periods_in(
    start: dt.date, end: dt.date, group: Grouping, start_day: int
) -> list[tuple[dt.date, dt.date]]:
    """The stretches of a report: financial months, calendar years or the whole range, each
    cut to the range."""
    if group == "total" or start > end:
        return [(start, end)]
    result: list[tuple[dt.date, dt.date]] = []
    if group == "year":
        for year in range(start.year, end.year + 1):
            result.append((max(start, dt.date(year, 1, 1)), min(end, dt.date(year, 12, 31))))
        return result
    first, _ = period_of(start, start_day)
    while first <= end:
        following = shift(first, 1, start_day)
        result.append((max(start, first), min(end, following - _DAY)))
        first = following
    return result


def cash_flow(
    db: Session, user: User, start: dt.date, end: dt.date, group: Grouping
) -> list[Period]:
    """Income and expenses of each stretch. Transfers, adjustments and buying or selling
    investments are neither."""
    result = []
    for first, last in periods_in(start, end, group, user.month_start_day):
        income, expenses = db.execute(
            select(
                func.coalesce(func.sum(Transaction.amount).filter(Transaction.kind == "income"), 0),
                func.coalesce(
                    func.sum(Transaction.amount).filter(Transaction.kind == "expense"), 0
                ),
            ).where(Transaction.user_id == user.id, Transaction.date.between(first, last))
        ).one()
        result.append(Period(first, last, Decimal(income), Decimal(expenses)))
    return result


# --- Spending ---------------------------------------------------------------------------------


def _year_before(date: dt.date) -> dt.date:
    try:
        return date.replace(year=date.year - 1)
    except ValueError:  # 29 February
        return date.replace(year=date.year - 1, day=28)


@dataclass(frozen=True)
class Ranges:
    current: tuple[dt.date, dt.date]
    previous: tuple[dt.date, dt.date]
    last_year: tuple[dt.date, dt.date]


def comparison_ranges(start: dt.date, end: dt.date, today: dt.date, start_day: int) -> Ranges:
    """The range up to today, and what to compare it with: the previous financial month (or
    year, or as many days just before) and the same dates a year earlier. A month still under
    way is compared with the same number of days of the previous one."""
    stop = max(min(end, today), start)
    length = stop - start
    if period_of(start, start_day) == (start, end):
        previous_start = shift(start, -1, start_day)
    elif (start.month, start.day, end.month, end.day) == (1, 1, 12, 31) and start.year == end.year:
        previous_start = dt.date(start.year - 1, 1, 1)
    else:
        previous_start = start - length - _DAY
    # A finished range takes the whole previous one; one under way, as many days of it.
    previous_end = start - _DAY if stop == end else min(previous_start + length, start - _DAY)
    return Ranges(
        current=(start, stop),
        previous=(previous_start, previous_end),
        last_year=(_year_before(start), _year_before(stop)),
    )


@dataclass
class SpendLine:
    key: str
    label: str
    icon: str | None = None
    amounts: list[Decimal] = field(default_factory=lambda: [_ZERO, _ZERO, _ZERO])
    children: list[SpendLine] = field(default_factory=list)


def _expenses(user: User, first: dt.date, last: dt.date) -> tuple[ColumnElement[bool], ...]:
    return (
        Transaction.user_id == user.id,
        Transaction.kind == "expense",
        Transaction.date.between(first, last),
    )


def _by_category(db: Session, user: User, ranges: list[tuple[dt.date, dt.date]]) -> list[SpendLine]:
    categories = {c.id: c for c in db.scalars(owned(Category, user))}
    tops: dict[str, SpendLine] = {}
    for index, (first, last) in enumerate(ranges):
        rows = db.execute(
            select(Transaction.category_id, func.sum(Transaction.amount))
            .where(*_expenses(user, first, last))
            .group_by(Transaction.category_id)
        )
        for category_id, total in rows:
            amount = -Decimal(total)
            category = categories.get(category_id) if category_id else None
            parent = categories.get(category.parent_id) if category and category.parent_id else None
            top = parent or category
            key = str(top.id) if top else "none"
            line = tops.setdefault(
                key,
                SpendLine(key, top.name if top else "Sin categoría", top.icon if top else None),
            )
            line.amounts[index] += amount
            if parent is not None and category is not None:
                child = next((c for c in line.children if c.key == str(category.id)), None)
                if child is None:
                    child = SpendLine(str(category.id), category.name, category.icon)
                    line.children.append(child)
                child.amounts[index] += amount
    return list(tops.values())


def _merchant_label(text: str) -> str:
    return text.title() if text.isupper() else text


def _by_merchant(db: Session, user: User, ranges: list[tuple[dt.date, dt.date]]) -> list[SpendLine]:
    lines: dict[str, SpendLine] = {}
    for index, (first, last) in enumerate(ranges):
        rows = db.execute(
            select(Transaction.description, func.sum(Transaction.amount))
            .where(*_expenses(user, first, last))
            .group_by(Transaction.description)
        )
        for description, total in rows:
            merchant = suggest_match_text(description or "") or ""
            key = merchant.casefold()
            line = lines.setdefault(key, SpendLine(key, _merchant_label(merchant)))
            line.amounts[index] += -Decimal(total)
    return list(lines.values())


def _by_tag(db: Session, user: User, ranges: list[tuple[dt.date, dt.date]]) -> list[SpendLine]:
    lines: dict[str, SpendLine] = {}
    tag = func.unnest(Transaction.tags).label("tag")
    for index, (first, last) in enumerate(ranges):
        tagged = select(tag, Transaction.amount).where(*_expenses(user, first, last)).subquery()
        rows = db.execute(select(tagged.c.tag, func.sum(tagged.c.amount)).group_by(tagged.c.tag))
        for name, total in rows:
            line = lines.setdefault(name, SpendLine(name, name))
            line.amounts[index] += -Decimal(total)
    return list(lines.values())


def _sorted(lines: Iterable[SpendLine]) -> list[SpendLine]:
    kept = [line for line in lines if line.amounts[0] or line.amounts[1]]
    for line in kept:
        line.children = _sorted(line.children)
    return sorted(kept, key=lambda line: (-line.amounts[0], -line.amounts[1], line.label))


def spending(db: Session, user: User, ranges: Ranges, by: SpendingBy) -> list[SpendLine]:
    """Expenses grouped, for the current range and the two to compare with. Lines that had
    nothing in the current range nor the previous one are left out."""
    stretches = [ranges.current, ranges.previous, ranges.last_year]
    if by == "category":
        lines = _by_category(db, user, stretches)
    elif by == "merchant":
        lines = _by_merchant(db, user, stretches)
    else:
        lines = _by_tag(db, user, stretches)
    return _sorted(lines)


def totals(db: Session, user: User, ranges: Ranges) -> list[Decimal]:
    """All the expenses of each range, positive."""
    result = []
    for first, last in (ranges.current, ranges.previous, ranges.last_year):
        total = db.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                *_expenses(user, first, last)
            )
        )
        result.append(-Decimal(total or 0))
    return result

"""Budgets (RF-PRS-01…04): limits per category or zero-based, by financial month.

Every line is a budgeted expense category. A main category's line also covers its
subcategories, except those with a line of their own, so nothing counts twice.

For each line and month:
    available = carried from the month before + assigned + activity
where activity is what was spent (negative) or refunded (positive) in the line's categories.

- Limits: "assigned" is the cap, which holds until changed. Carrying the leftover or the
  overspending to the next month is optional (`budget_rollover`).
- Zero-based: "assigned" is what was put that month, and the balance always carries over. The
  money left to assign is the available cash minus what the lines hold:
      to_assign + Σ available = cash
  where cash is the balance of the everyday accounts minus what goals hold (iteration 5).
"""

import datetime as dt
import uuid
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import clock, ledger
from app.models.accounts import Account
from app.models.budgets import BudgetAssignment
from app.models.goals import GoalAccount, GoalContribution, SavingsGoal
from app.models.transactions import Category, Transaction
from app.models.user import User
from app.ownership import owned
from finance.periods import period_of, shift

# Accounts whose money is for everyday spending: what a zero-based budget distributes.
EVERYDAY_KINDS = ("checking", "savings", "cash", "wallet", "credit_card")
_ZERO = Decimal("0.00")


@dataclass(frozen=True)
class Line:
    category_id: uuid.UUID
    assigned: Decimal
    activity: Decimal
    carried: Decimal

    @property
    def available(self) -> Decimal:
        return self.carried + self.assigned + self.activity


@dataclass(frozen=True)
class BudgetMonth:
    start: dt.date
    end: dt.date
    lines: list[Line]
    unbudgeted: Decimal  # spending in categories without a line (and uncategorised)
    cash: Decimal | None  # zero-based only
    to_assign: Decimal | None  # zero-based only


@dataclass
class _Context:
    user: User
    start_day: int
    zero_based: bool
    rollover: bool
    rows: list[BudgetAssignment]
    categories: dict[uuid.UUID, Category]

    def period(self, date: dt.date) -> dt.date:
        return period_of(date, self.start_day)[0]


def _context(db: Session, user: User) -> _Context:
    zero_based = user.budget_mode == "zero_based"
    return _Context(
        user=user,
        start_day=user.month_start_day,
        zero_based=zero_based,
        rollover=zero_based or user.budget_rollover,
        rows=list(db.scalars(owned(BudgetAssignment, user))),
        categories={
            c.id: c for c in db.scalars(owned(Category, user).where(Category.kind == "expense"))
        },
    )


def _assigned(ctx: _Context, category_id: uuid.UUID, period: dt.date) -> Decimal:
    rows = [r for r in ctx.rows if r.category_id == category_id]
    if ctx.zero_based:
        return sum((r.amount for r in rows if ctx.period(r.month) == period), _ZERO)
    # A limit holds from its month on, until a later one replaces it.
    earlier = [r for r in rows if ctx.period(r.month) <= period]
    return max(earlier, key=lambda r: r.month).amount if earlier else _ZERO


def _line_ids(ctx: _Context, period: dt.date) -> list[uuid.UUID]:
    """Categories budgeted in this month."""
    started = {r.category_id for r in ctx.rows if ctx.period(r.month) <= period}
    ids = [
        c
        for c in started
        if c in ctx.categories and (ctx.zero_based or _assigned(ctx, c, period) > 0)
    ]

    # Main categories first, then by name, like the category lists.
    def order(category_id: uuid.UUID) -> tuple[str, int, str]:
        category = ctx.categories[category_id]
        parent = ctx.categories.get(category.parent_id) if category.parent_id else None
        main = parent or category
        return (main.name.lower(), 0 if parent is None else 1, category.name.lower())

    return sorted(ids, key=order)


def _line_for(
    ctx: _Context, lines: set[uuid.UUID], category_id: uuid.UUID | None
) -> uuid.UUID | None:
    """The line a movement of this category counts in: its own, or its main category's."""
    if category_id is None or category_id not in ctx.categories:
        return None
    if category_id in lines:
        return category_id
    parent = ctx.categories[category_id].parent_id
    return parent if parent in lines else None


def _activity(
    db: Session, ctx: _Context, lines: set[uuid.UUID], since: dt.date, until: dt.date
) -> tuple[dict[tuple[uuid.UUID, dt.date], Decimal], dict[dt.date, Decimal]]:
    """Spending per (line, month) and spending outside the budget per month."""
    rows = db.execute(
        select(
            Transaction.category_id,
            Transaction.kind,
            Transaction.date,
            func.sum(Transaction.amount),
        )
        .where(
            Transaction.user_id == ctx.user.id,
            Transaction.kind.in_(("expense", "income")),
            Transaction.date.between(since, until),
        )
        .group_by(Transaction.category_id, Transaction.kind, Transaction.date)
    )
    by_line: dict[tuple[uuid.UUID, dt.date], Decimal] = defaultdict(lambda: _ZERO)
    outside: dict[dt.date, Decimal] = defaultdict(lambda: _ZERO)
    for category_id, kind, date, total in rows:
        period = ctx.period(date)
        line = _line_for(ctx, lines, category_id)
        if line is not None:
            by_line[(line, period)] += Decimal(total)  # refunds included
        elif category_id in ctx.categories or (category_id is None and kind == "expense"):
            # An unbudgeted expense category, or an expense without category. Income
            # categories are not budget lines: income raises the cash instead.
            outside[period] += Decimal(total)
    return by_line, outside


def month(db: Session, user: User, date: dt.date) -> BudgetMonth:
    ctx = _context(db, user)
    start, end = period_of(date, ctx.start_day)
    line_ids = _line_ids(ctx, start)
    lines = set(line_ids)

    first = {c: min(ctx.period(r.month) for r in ctx.rows if r.category_id == c) for c in line_ids}
    since = min(first.values(), default=start) if ctx.rollover else start
    activity, outside = _activity(db, ctx, lines, since, end)

    result = []
    for category_id in line_ids:
        carried = _ZERO
        period = first[category_id] if ctx.rollover else start
        while period < start:
            carried += _assigned(ctx, category_id, period) + activity[(category_id, period)]
            period = shift(period, 1, ctx.start_day)
        result.append(
            Line(
                category_id=category_id,
                assigned=_assigned(ctx, category_id, start),
                activity=activity[(category_id, start)],
                carried=carried,
            )
        )

    cash = to_assign = None
    if ctx.zero_based:
        cash = everyday_cash(db, user, min(end, clock.today()))
        to_assign = cash - sum((line.available for line in result), _ZERO)
    return BudgetMonth(
        start=start,
        end=end,
        lines=result,
        unbudgeted=outside[start],
        cash=cash,
        to_assign=to_assign,
    )


def everyday_cash(db: Session, user: User, on: dt.date) -> Decimal:
    """Money in everyday accounts at the end of a day, minus what goals hold in them.
    Accounts a goal owns whole are left out entirely."""
    whole = set(
        db.scalars(
            select(GoalAccount.account_id)
            .join(SavingsGoal, SavingsGoal.id == GoalAccount.goal_id)
            .where(SavingsGoal.user_id == user.id)
        )
    )
    accounts = [
        a
        for a in db.scalars(
            owned(Account, user).where(
                Account.kind.in_(EVERYDAY_KINDS), Account.archived_at.is_(None)
            )
        )
        if a.id not in whole
    ]
    balances = sum((ledger.balance_on(db, a, on) for a in accounts), _ZERO)
    held = db.scalar(
        select(func.coalesce(func.sum(GoalContribution.amount), 0)).where(
            GoalContribution.user_id == user.id,
            GoalContribution.account_id.in_([a.id for a in accounts]),
            GoalContribution.date <= on,
        )
    )
    return balances - Decimal(held or 0)


# --- Changes ----------------------------------------------------------------------------------


def set_amount(
    db: Session, user: User, date: dt.date, category_id: uuid.UUID, amount: Decimal
) -> None:
    """Assign (zero-based) or set the limit (limits) of a category for the month of `date`."""
    start = period_of(date, user.month_start_day)[0]
    row = db.scalar(
        owned(BudgetAssignment, user).where(
            BudgetAssignment.month == start, BudgetAssignment.category_id == category_id
        )
    )
    if row is None:
        row = BudgetAssignment(user_id=user.id, month=start, category_id=category_id, amount=amount)
        db.add(row)
    else:
        row.amount = amount


def add_amount(
    db: Session, user: User, date: dt.date, category_id: uuid.UUID, amount: Decimal
) -> None:
    current = month_assigned(db, user, date, category_id)
    set_amount(db, user, date, category_id, current + amount)


def month_assigned(db: Session, user: User, date: dt.date, category_id: uuid.UUID) -> Decimal:
    """What was assigned this month only (zero-based)."""
    start = period_of(date, user.month_start_day)[0]
    rows = db.scalars(
        owned(BudgetAssignment, user).where(BudgetAssignment.category_id == category_id)
    )
    return sum(
        (r.amount for r in rows if period_of(r.month, user.month_start_day)[0] == start), _ZERO
    )


def remove_line(db: Session, user: User, category_id: uuid.UUID) -> None:
    """Take a category out of the budget, history included (zero-based)."""
    for row in db.scalars(
        owned(BudgetAssignment, user).where(BudgetAssignment.category_id == category_id)
    ):
        db.delete(row)

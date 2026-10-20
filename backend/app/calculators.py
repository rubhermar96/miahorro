"""The user's own figures for the calculators: averages of the last complete financial months,
money available and loan instalments (RF-CAL, prefill)."""

import datetime as dt
import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import budgets, loans
from app.goals import savings_periods
from app.models.loans import Loan, ReferenceRate
from app.models.transactions import Category, Transaction
from app.models.user import User
from app.ownership import owned
from finance.money import round_cents

_ZERO = Decimal(0)
MONTHS = 3


@dataclass(frozen=True)
class CategoryAverage:
    id: uuid.UUID | None  # None: uncategorised
    name: str
    icon: str | None
    monthly: Decimal  # positive


@dataclass(frozen=True)
class Context:
    months: int
    start: dt.date | None
    end: dt.date | None
    income: Decimal
    expenses: Decimal  # positive
    liquidity: Decimal
    loan_payments: Decimal
    categories: list[CategoryAverage]
    euribor: tuple[dt.date, Decimal] | None


def context(db: Session, user: User, today: dt.date) -> Context:
    # The current month is not over: only complete ones, and only those with movements, so a
    # recent start does not drag the averages down.
    periods = [
        p for p in savings_periods(db, user, today, MONTHS + 1)[:-1] if p.income or p.expenses
    ]
    months = len(periods)
    start = periods[0].start if periods else None
    end = periods[-1].end if periods else None
    income = sum((p.income for p in periods), _ZERO)
    expenses = -sum((p.expenses for p in periods), _ZERO)
    categories = (
        _by_category(db, user, start, end, months) if start is not None and end is not None else []
    )
    return Context(
        months=months,
        start=start,
        end=end,
        income=round_cents(income / months) if months else _ZERO,
        expenses=round_cents(expenses / months) if months else _ZERO,
        liquidity=budgets.everyday_cash(db, user, today),
        loan_payments=_loan_payments(db, user, today),
        categories=categories,
        euribor=_latest_euribor(db),
    )


def _by_category(
    db: Session, user: User, start: dt.date, end: dt.date, months: int
) -> list[CategoryAverage]:
    top = func.coalesce(Category.parent_id, Category.id)
    totals = {
        group: Decimal(total)
        for group, total in db.execute(
            select(top, func.sum(Transaction.amount))
            .select_from(Transaction)
            .outerjoin(Category, Category.id == Transaction.category_id)
            .where(
                Transaction.user_id == user.id,
                Transaction.kind == "expense",
                Transaction.date.between(start, end),
            )
            .group_by(top)
        )
    }
    names = {
        c.id: c
        for c in db.scalars(owned(Category, user).where(Category.id.in_(k for k in totals if k)))
    }
    result = [
        CategoryAverage(
            id=group,
            name=names[group].name if group in names else "Sin categoría",
            icon=names[group].icon if group in names else None,
            monthly=round_cents(-total / months),
        )
        for group, total in totals.items()
        if group is None or group in names
    ]
    return sorted(result, key=lambda c: c.monthly, reverse=True)


def _loan_payments(db: Session, user: User, today: dt.date) -> Decimal:
    total = _ZERO
    for loan in db.scalars(
        owned(Loan, user).where(Loan.archived_at.is_(None), Loan.kind != "p2p_lent")
    ):
        rows, _ = loans.table(db, loan, today)
        summary = loans.summarize(loan, rows, loans.prepayments_of(db, loan), today)
        if summary.next_payment is not None:
            total += summary.next_payment.payment
    return total


def _latest_euribor(db: Session) -> tuple[dt.date, Decimal] | None:
    row = db.scalar(
        select(ReferenceRate)
        .where(ReferenceRate.index == "euribor_12m")
        .order_by(ReferenceRate.month.desc())
        .limit(1)
    )
    return (row.month, row.value) if row else None

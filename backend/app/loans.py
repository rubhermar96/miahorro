"""Loans (RF-PRE-01…09): the rate at each review, the amortization table and the summary.

A variable or mixed loan keeps its initial rate for `fixed_months`; then, every `review_months`,
its rate becomes the reference index plus the spread (never below 0 %). The index value used is
the latest one typed in for a month before the review. A review with no value yet keeps the
previous rate and is reported, so the table is never silently wrong.
"""

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.loans import Loan, LoanPrepayment, ReferenceRate
from finance.loans import (
    Installment,
    Prepayment,
    PrepaymentMode,
    add_months,
    early_repayment_fee,
    legal_fee_cap,
    schedule,
)

_ZERO = Decimal("0.00")


@dataclass
class Rates:
    rate_on: Callable[[int, dt.date], Decimal]
    reviews: list[tuple[int, dt.date, Decimal, dt.date | None]] = field(default_factory=list)
    # (instalment number, date, rate, month of the index value used; None if missing)
    warnings: list[str] = field(default_factory=list)


def _index_values(db: Session, index: str) -> list[tuple[dt.date, Decimal]]:
    rows = db.execute(
        select(ReferenceRate.month, ReferenceRate.value)
        .where(ReferenceRate.index == index)
        .order_by(ReferenceRate.month)
    )
    return [(month, value) for month, value in rows]


def rates_for(db: Session, loan: Loan, today: dt.date) -> Rates:
    if loan.rate_type == "fixed" or loan.index is None:
        return Rates(rate_on=lambda number, date: loan.fixed_rate)

    values = _index_values(db, loan.index)
    spread = loan.spread or _ZERO
    result = Rates(rate_on=lambda number, date: loan.fixed_rate)
    changes: list[tuple[int, Decimal]] = [(1, loan.fixed_rate)]
    number = loan.fixed_months + 1
    current = loan.fixed_rate
    while number <= loan.term_months:
        date = add_months(loan.first_payment, number - 1, loan.first_payment.day)
        review_month = date.replace(day=1)
        known = [(month, value) for month, value in values if month < review_month]
        if known:
            month, value = known[-1]
            current = max(value + spread, _ZERO)
            result.reviews.append((number, date, current, month))
            if date <= today and month < add_months(review_month, -3):
                result.warnings.append(
                    f"Para la revisión del {date:%d/%m/%Y} se ha usado el Euribor de "
                    f"{month:%m/%Y}: añade los meses que faltan."
                )
        else:
            result.reviews.append((number, date, current, None))
            if date <= today:
                result.warnings.append(
                    f"Falta el Euribor para la revisión del {date:%d/%m/%Y}: se mantiene el "
                    "tipo anterior."
                )
        changes.append((number, current))
        number += loan.review_months

    def rate_on(number: int, date: dt.date) -> Decimal:
        rate = loan.fixed_rate
        for start, value in changes:
            if start <= number:
                rate = value
        return rate

    result.rate_on = rate_on
    return result


def prepayments_of(db: Session, loan: Loan) -> list[Prepayment]:
    rows = db.scalars(
        select(LoanPrepayment)
        .where(LoanPrepayment.loan_id == loan.id)
        .order_by(LoanPrepayment.date)
    )
    return [Prepayment(r.date, r.amount, r.mode) for r in rows]  # type: ignore[arg-type]


def table(
    db: Session, loan: Loan, today: dt.date, extra: list[Prepayment] | None = None
) -> tuple[list[Installment], Rates]:
    rates = rates_for(db, loan, today)
    rows = schedule(
        loan.principal,
        loan.first_payment,
        loan.term_months,
        rates.rate_on,
        system=loan.system,  # type: ignore[arg-type]  # constrained in the database
        grace_months=loan.grace_months,
        prepayments=[*prepayments_of(db, loan), *(extra or [])],
    )
    return rows, rates


@dataclass(frozen=True)
class Summary:
    outstanding: Decimal
    principal_paid: Decimal
    interest_paid: Decimal
    interest_left: Decimal
    next_payment: Installment | None
    end_date: dt.date | None
    payments_left: int
    current_rate: Decimal


def summarize(
    loan: Loan, rows: list[Installment], prepaid: list[Prepayment], today: dt.date
) -> Summary:
    paid = [r for r in rows if r.date <= today]
    left = [r for r in rows if r.date > today]
    # Early repayments already made count today, though the table applies them at the next
    # instalment.
    since = paid[-1].date if paid else dt.date.min
    repaid_early = sum((p.amount for p in prepaid if since < p.date <= today), _ZERO)
    outstanding = (paid[-1].outstanding if paid else loan.principal) - repaid_early
    current = paid[-1].rate if paid else (left[0].rate if left else loan.fixed_rate)
    return Summary(
        outstanding=max(outstanding, _ZERO),
        principal_paid=loan.principal - max(outstanding, _ZERO),
        interest_paid=sum((r.interest for r in paid), _ZERO),
        interest_left=sum((r.interest for r in left), _ZERO),
        next_payment=left[0] if left else None,
        end_date=rows[-1].date if rows else None,
        payments_left=len(left),
        current_rate=current,
    )


@dataclass(frozen=True)
class Simulation:
    fee: Decimal
    fee_percent: Decimal
    legal_cap: Decimal | None
    interest_saved: Decimal
    payment_before: Decimal | None
    payment_after: Decimal | None
    end_before: dt.date | None
    end_after: dt.date | None
    payments_saved: int


def fee_for(
    loan: Loan, rows: list[Installment], date: dt.date, amount: Decimal
) -> tuple[Decimal, Decimal, Decimal | None]:
    """The early repayment fee: the contract's, up to the legal cap."""
    months_left = len([r for r in rows if r.date > date])
    fixed_until = (
        add_months(loan.first_payment, loan.fixed_months, loan.first_payment.day)
        if loan.fixed_months
        else None
    )
    cap = legal_fee_cap(
        loan.kind, loan.rate_type, loan.signed_on, date, months_left, fixed_until=fixed_until
    )
    percent = loan.early_repayment_fee if cap is None else min(loan.early_repayment_fee, cap)
    return early_repayment_fee(amount, loan.early_repayment_fee, cap), percent, cap


def simulate(
    db: Session, loan: Loan, today: dt.date, date: dt.date, amount: Decimal, mode: PrepaymentMode
) -> Simulation:
    before, _ = table(db, loan, today)
    after, _ = table(db, loan, today, extra=[Prepayment(date, amount, mode)])
    fee, percent, cap = fee_for(loan, before, date, amount)
    next_before = next((r for r in before if r.date >= date), None)
    next_after = next((r for r in after if r.date >= date), None)
    return Simulation(
        fee=fee,
        fee_percent=percent,
        legal_cap=cap,
        interest_saved=sum((r.interest for r in before), _ZERO)
        - sum((r.interest for r in after), _ZERO),
        payment_before=next_before.payment if next_before else None,
        payment_after=next_after.payment if next_after else None,
        end_before=before[-1].date if before else None,
        end_after=after[-1].date if after else None,
        payments_saved=len(before) - len(after),
    )

"""Loan amortization (RF-PRE-05, RF-PRE-07): French and linear systems, grace periods, rate
changes and early repayments. Pure functions on exact decimals, reused by the calculators.

Conventions, as Spanish banks do:
- Monthly instalments; the monthly rate is the nominal annual rate (TIN) / 12.
- Interest is rounded to the cent every month (ROUND_HALF_UP).
- The French instalment is recomputed on the outstanding capital and the instalments left
  whenever the rate changes or an early repayment reduces the instalment.
- The last instalment absorbs the rounding, so the capital ends exactly at zero.
"""

import calendar
import datetime as dt
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from typing import Literal

from finance.money import round_cents

type System = Literal["french", "linear"]
type PrepaymentMode = Literal["reduce_payment", "reduce_term"]

_ZERO = Decimal("0.00")
_MONTHS_PER_YEAR = Decimal(12)
_HUNDRED = Decimal(100)
_SLIVER = Decimal("0.05")  # of an instalment


@dataclass(frozen=True)
class Installment:
    number: int  # 1-based
    date: dt.date
    rate: Decimal  # annual nominal rate in force, in percent
    payment: Decimal
    interest: Decimal
    principal: Decimal
    outstanding: Decimal  # capital left after this instalment


@dataclass(frozen=True)
class Prepayment:
    date: dt.date
    amount: Decimal
    mode: PrepaymentMode


def add_months(date: dt.date, months: int, day: int | None = None) -> dt.date:
    """Same day `months` later, or the month's last day if it is shorter."""
    total = date.month - 1 + months
    year, month = date.year + total // 12, total % 12 + 1
    wanted = day or date.day
    return dt.date(year, month, min(wanted, calendar.monthrange(year, month)[1]))


def monthly_rate(annual_percent: Decimal) -> Decimal:
    return annual_percent / _HUNDRED / _MONTHS_PER_YEAR


def french_payment(principal: Decimal, annual_percent: Decimal, months: int) -> Decimal:
    """The fixed instalment that repays `principal` in `months` (Excel's PAGO)."""
    if months <= 0:
        return round_cents(principal)
    rate = monthly_rate(annual_percent)
    if rate == 0:
        return round_cents(principal / months)
    factor = (1 + rate) ** months
    return round_cents(principal * rate * factor / (factor - 1))


def months_to_repay(principal: Decimal, annual_percent: Decimal, payment: Decimal) -> int:
    """Instalments of `payment` needed to repay `principal` (Excel's NPER, rounded up)."""
    if principal <= 0:
        return 0
    rate = monthly_rate(annual_percent)
    if rate == 0:
        return int((principal / payment).to_integral_value(rounding=ROUND_CEILING))
    interest = principal * rate
    if payment <= interest:
        raise ValueError("La cuota no cubre los intereses: el préstamo no se acabaría de pagar.")
    # n = -ln(1 - P·r / payment) / ln(1 + r)
    ratio = 1 - interest / payment
    n = -ratio.ln() / (1 + rate).ln()
    # A sliver of an instalment (the instalment was rounded down to the cent) goes into the
    # last one instead of adding a month: 805,23 € repays 150.000 € at 5 % in 360, not 361.
    whole = int(n)
    return whole if n - whole < _SLIVER else whole + 1


def schedule(
    principal: Decimal,
    first_payment: dt.date,
    months: int,
    rate_on: Callable[[int, dt.date], Decimal],
    *,
    system: System = "french",
    grace_months: int = 0,
    prepayments: Sequence[Prepayment] = (),
) -> list[Installment]:
    """The full amortization table.

    `rate_on(number, date)` gives the annual rate (percent) of each instalment, so fixed,
    variable and mixed loans share this code. During the grace months only interest is paid.
    An early repayment lowers the capital just before the first instalment on or after its
    date; then either the instalment or the number of instalments goes down.
    """
    if principal <= 0 or months <= 0:
        return []
    pending = sorted(prepayments, key=lambda p: p.date)
    outstanding = principal
    left = months  # instalments still to pay, grace ones included
    payment = _ZERO  # French instalment
    share = _ZERO  # linear: capital repaid each month
    previous_rate: Decimal | None = None
    previous_date = dt.date.min
    rows: list[Installment] = []
    number = 0
    while outstanding > 0 and left > 0:
        number += 1
        date = add_months(first_payment, number - 1, first_payment.day)
        rate = rate_on(number, date)
        grace_left = max(grace_months - number + 1, 0)

        recompute = number == grace_months + 1 or (system == "french" and rate != previous_rate)
        while pending and pending[0].date <= date:
            early = pending.pop(0)
            if early.date <= previous_date:
                continue  # before the loan started paying: not part of this table
            outstanding = max(outstanding - early.amount, _ZERO)
            if outstanding == 0:
                break
            amortizing = payment if system == "french" else share
            if early.mode == "reduce_term" and amortizing > 0:
                needed = (
                    months_to_repay(outstanding, rate, payment)
                    if system == "french"
                    else int((outstanding / share).to_integral_value(rounding=ROUND_CEILING))
                )
                left = grace_left + needed
            else:
                recompute = True  # same term, smaller instalment
        if outstanding == 0:
            break

        if recompute and grace_left == 0:
            amortizing_left = left
            payment = french_payment(outstanding, rate, amortizing_left)
            share = round_cents(outstanding / amortizing_left)

        interest = round_cents(outstanding * monthly_rate(rate))
        if grace_left > 0:
            repaid = _ZERO
        elif system == "linear":
            repaid = share
        else:
            repaid = max(payment - interest, _ZERO)
        if left == 1 or repaid >= outstanding:
            repaid = outstanding  # the last one absorbs the rounding
        outstanding -= repaid
        rows.append(
            Installment(
                number=number,
                date=date,
                rate=rate,
                payment=interest + repaid,
                interest=interest,
                principal=repaid,
                outstanding=outstanding,
            )
        )
        left -= 1
        previous_rate = rate
        previous_date = date
    return rows


# --- Early repayment fees ---------------------------------------------------------------------


def legal_fee_cap(
    kind: str,
    rate_type: str,
    signed_on: dt.date,
    on: dt.date,
    months_left: int,
    *,
    fixed_until: dt.date | None = None,
) -> Decimal | None:
    """The maximum early repayment fee the law allows, in percent; None if no cap applies.

    - Mortgages (Ley 5/2019, art. 23): fixed rate, 2 % in the first 10 years and 1.5 % after;
      variable, 0.25 % in the first 3 years, 0.15 % up to 5 and nothing after. A mixed loan
      follows the fixed rule during its fixed period.
    - Consumer loans (Ley 16/2011, art. 30): 1 %, or 0.5 % with a year or less to go.
    - Loans between individuals: what the parties agreed.
    """
    years = (on - signed_on).days / 365.25
    if kind == "mortgage":
        fixed = rate_type == "fixed" or (
            rate_type == "mixed" and fixed_until is not None and on < fixed_until
        )
        if fixed:
            return Decimal(2) if years < 10 else Decimal("1.5")
        if years < 3:
            return Decimal("0.25")
        return Decimal("0.15") if years < 5 else Decimal(0)
    if kind in ("personal", "car", "consumer", "credit_line"):
        return Decimal(1) if months_left > 12 else Decimal("0.5")
    return None


def early_repayment_fee(amount: Decimal, contract_percent: Decimal, cap: Decimal | None) -> Decimal:
    percent = contract_percent if cap is None else min(contract_percent, cap)
    return round_cents(amount * percent / _HUNDRED)

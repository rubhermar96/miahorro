"""Saving calculators: compound interest (RF-CAL-01), savings target (RF-CAL-02) and emergency
fund (RF-CAL-10).

Conventions: the return is an effective annual rate (TAE), compounded monthly with the
equivalent monthly rate, and contributions go in at the start of each month.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from typing import Literal

from finance.money import CENT, round_cents
from finance.taxes import Bracket, progressive_tax

type TaxMode = Literal["none", "yearly", "end"]

_ZERO = Decimal(0)
_ONE = Decimal(1)
_HUNDRED = Decimal(100)
MAX_MONTHS = 1200  # a century: beyond that the answer is "never"


def monthly_return(annual_percent: Decimal) -> Decimal:
    """The monthly rate equivalent to an effective annual one: (1 + r)^(1/12) - 1."""
    if annual_percent == 0:
        return _ZERO
    return (_ONE + annual_percent / _HUNDRED) ** (_ONE / 12) - _ONE


# --- Compound interest ------------------------------------------------------------------------


@dataclass(frozen=True)
class CompoundYear:
    year: int
    contributed: Decimal  # cumulative, the initial capital included
    gains: Decimal  # cumulative returns, net of the taxes already paid
    tax: Decimal  # cumulative tax paid
    balance: Decimal
    real_balance: Decimal  # in today's money


@dataclass(frozen=True)
class Compound:
    years: list[CompoundYear]
    contributed: Decimal
    gains: Decimal  # before taxes
    tax: Decimal
    final: Decimal  # after taxes
    final_real: Decimal


def compound(
    initial: Decimal,
    monthly: Decimal,
    annual_return: Decimal,
    years: int,
    *,
    inflation: Decimal = _ZERO,
    yearly_increase: Decimal = _ZERO,
    tax_mode: TaxMode = "none",
    brackets: Sequence[Bracket] = (),
) -> Compound:
    """Grow `initial` plus a monthly contribution for `years`.

    Taxes on the gains use the savings scale (`brackets`): `yearly` taxes each year's gains
    (deposits, accounts: interest is taxed when paid); `end` taxes all the gains at the end
    (funds: taxed only when sold). The contribution grows `yearly_increase` % each year.
    """
    rate = monthly_return(annual_return)
    balance = initial
    contributed = initial
    tax_paid = _ZERO
    rows: list[CompoundYear] = []
    for year in range(1, years + 1):
        start_balance = balance
        contribution = round_cents(monthly * (_ONE + yearly_increase / _HUNDRED) ** (year - 1))
        for _ in range(12):
            balance = (balance + contribution) * (_ONE + rate)
        contributed += contribution * 12
        if tax_mode == "yearly":
            year_gain = balance - start_balance - contribution * 12
            tax = progressive_tax(year_gain, brackets)
            balance -= tax
            tax_paid += tax
        deflator = (_ONE + inflation / _HUNDRED) ** year
        rows.append(
            CompoundYear(
                year=year,
                contributed=round_cents(contributed),
                gains=round_cents(balance - contributed),
                tax=round_cents(tax_paid),
                balance=round_cents(balance),
                real_balance=round_cents(balance / deflator),
            )
        )
    gains_before_tax = balance - contributed + tax_paid
    if tax_mode == "end":
        tax = progressive_tax(balance - contributed, brackets)
        balance -= tax
        tax_paid += tax
    deflator = (_ONE + inflation / _HUNDRED) ** years
    return Compound(
        years=rows,
        contributed=round_cents(contributed),
        gains=round_cents(gains_before_tax),
        tax=round_cents(tax_paid),
        final=round_cents(balance),
        final_real=round_cents(balance / deflator),
    )


# --- Savings target ---------------------------------------------------------------------------


def future_value(initial: Decimal, monthly: Decimal, rate: Decimal, months: int) -> Decimal:
    """What `initial` plus `monthly` at the start of each month become after `months`."""
    if rate == 0:
        return initial + monthly * months
    growth = (_ONE + rate) ** months
    return initial * growth + monthly * (_ONE + rate) * (growth - _ONE) / rate


def required_monthly(
    target: Decimal, initial: Decimal, months: int, annual_return: Decimal
) -> Decimal:
    """Monthly saving needed to have `target` in `months` (rounded up to the cent)."""
    rate = monthly_return(annual_return)
    missing = target - future_value(initial, _ZERO, rate, months)
    if missing <= 0 or months <= 0:
        return Decimal("0.00")
    per_month = future_value(_ZERO, _ONE, rate, months)
    return (missing / per_month).quantize(CENT, rounding=ROUND_CEILING)


def months_to_target(
    target: Decimal, initial: Decimal, monthly: Decimal, annual_return: Decimal
) -> int | None:
    """Months until `target` is reached; None if not within a century."""
    rate = monthly_return(annual_return)
    balance = initial
    for month in range(MAX_MONTHS + 1):
        if balance >= target:
            return month
        balance = (balance + monthly) * (_ONE + rate)
    return None


# --- Emergency fund ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EmergencyFund:
    target: Decimal
    covered_months: Decimal  # one decimal
    missing: Decimal
    months_to_complete: int | None  # None: nothing missing, or no saving to complete it


def emergency_fund(
    essential_monthly: Decimal, months: int, current: Decimal, monthly_saving: Decimal
) -> EmergencyFund:
    target = round_cents(essential_monthly * months)
    covered = (
        (current / essential_monthly).quantize(Decimal("0.1"))
        if essential_monthly > 0
        else Decimal(0)
    )
    missing = max(target - current, _ZERO)
    to_complete = (
        int((missing / monthly_saving).to_integral_value(rounding=ROUND_CEILING))
        if missing > 0 and monthly_saving > 0
        else None
    )
    return EmergencyFund(
        target=target,
        covered_months=covered,
        missing=round_cents(missing),
        months_to_complete=to_complete,
    )

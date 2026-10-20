"""Mortgage comparison (RF-CAL-03): fixed, variable and mixed offers under several Euribor
scenarios, with and without the discounts (bonificaciones) for linked products.

A scenario keeps the Euribor constant from the first review on. The discount lowers the rate
of every period, and the linked products cost a yearly amount for the whole term.
"""

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from finance.loans import Installment, schedule
from finance.money import round_cents

type RateType = Literal["fixed", "variable", "mixed"]

_ZERO = Decimal(0)


@dataclass(frozen=True)
class Offer:
    name: str
    rate_type: RateType
    fixed_rate: Decimal  # the TIN, or the rate of the initial period
    fixed_months: int = 0  # variable and mixed: months at `fixed_rate`
    spread: Decimal = _ZERO  # over the Euribor
    discount: Decimal = _ZERO  # percentage points off with the linked products
    linked_yearly_cost: Decimal = _ZERO  # what those products cost a year
    upfront_costs: Decimal = _ZERO  # opening fee and the like


@dataclass(frozen=True)
class YearRow:
    year: int
    payment: Decimal  # last instalment of the year
    interest: Decimal
    principal: Decimal
    outstanding: Decimal


@dataclass(frozen=True)
class Outcome:
    first_payment: Decimal
    later_payment: Decimal | None  # after the initial period (variable and mixed)
    interest: Decimal
    linked_cost: Decimal
    total_cost: Decimal  # interest + linked products + upfront costs
    years: list[YearRow]


def _rate_on(offer: Offer, euribor: Decimal, discounted: bool) -> Callable[[int, dt.date], Decimal]:
    off = offer.discount if discounted else _ZERO

    def rate_on(number: int, _date: dt.date) -> Decimal:
        if offer.rate_type == "fixed" or number <= offer.fixed_months:
            rate = offer.fixed_rate - off
        else:
            rate = euribor + offer.spread - off
        return max(rate, _ZERO)

    return rate_on


def _by_year(rows: list[Installment]) -> list[YearRow]:
    years: list[YearRow] = []
    for start in range(0, len(rows), 12):
        chunk = rows[start : start + 12]
        years.append(
            YearRow(
                year=start // 12 + 1,
                payment=chunk[-1].payment,
                interest=sum((r.interest for r in chunk), _ZERO),
                principal=sum((r.principal for r in chunk), _ZERO),
                outstanding=chunk[-1].outstanding,
            )
        )
    return years


def outcome(
    principal: Decimal,
    months: int,
    offer: Offer,
    euribor: Decimal,
    *,
    discounted: bool,
    start: dt.date,
) -> Outcome:
    rows = schedule(principal, start, months, _rate_on(offer, euribor, discounted))
    interest = sum((r.interest for r in rows), _ZERO)
    linked = (
        round_cents(offer.linked_yearly_cost * Decimal(len(rows)) / 12) if discounted else _ZERO
    )
    later = None
    if offer.rate_type != "fixed" and offer.fixed_months < len(rows):
        later = rows[offer.fixed_months].payment
    return Outcome(
        first_payment=rows[0].payment if rows else _ZERO,
        later_payment=later,
        interest=interest,
        linked_cost=linked,
        total_cost=interest + linked + offer.upfront_costs,
        years=_by_year(rows),
    )

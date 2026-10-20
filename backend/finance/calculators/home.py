"""Buying a home (RF-CAL-04): taxes and costs of the purchase, the mortgage it needs, whether
the income bears it and the most it can cost.

Since Ley 5/2019 the bank pays the notary, registry and gestoría of the mortgage deed and the
AJD of the mortgage; the buyer pays the taxes and costs of the purchase deed and the
appraisal. A new home pays VAT (IGIC in Canarias) plus AJD; a second-hand one pays ITP.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from typing import Literal

from finance.loans import french_payment, monthly_rate
from finance.money import round_cents
from finance.taxes import Bracket, scale_tax

_ZERO = Decimal(0)
_ONE = Decimal(1)
_HUNDRED = Decimal(100)
_MAX_PRICE = Decimal(50_000_000)


@dataclass(frozen=True)
class PurchaseTax:
    brackets: Sequence[Bracket]  # ITP, VAT or IGIC
    marginal: bool = True  # ITP scales go by tranches; VAT and IGIC by band
    ajd: Decimal = _ZERO  # percent; new homes only


@dataclass(frozen=True)
class Fees:
    notary: Decimal
    registry: Decimal
    gestoria: Decimal
    appraisal: Decimal  # only with a mortgage
    agency_percent: Decimal = _ZERO


@dataclass(frozen=True)
class Purchase:
    tax: Decimal
    ajd: Decimal
    notary: Decimal
    registry: Decimal
    gestoria: Decimal
    appraisal: Decimal
    agency: Decimal
    costs: Decimal  # all of the above
    mortgage: Decimal
    down_payment: Decimal
    cash_needed: Decimal  # down payment + costs: the savings it takes


def purchase(price: Decimal, tax: PurchaseTax, fees: Fees, financed_percent: Decimal) -> Purchase:
    tax_amount = round_cents(scale_tax(price, tax.brackets, marginal=tax.marginal))
    ajd = round_cents(price * tax.ajd / _HUNDRED)
    mortgage = round_cents(price * financed_percent / _HUNDRED)
    appraisal = fees.appraisal if mortgage > 0 else _ZERO
    agency = round_cents(price * fees.agency_percent / _HUNDRED)
    costs = tax_amount + ajd + fees.notary + fees.registry + fees.gestoria + appraisal + agency
    down_payment = price - mortgage
    return Purchase(
        tax=tax_amount,
        ajd=ajd,
        notary=fees.notary,
        registry=fees.registry,
        gestoria=fees.gestoria,
        appraisal=appraisal,
        agency=agency,
        costs=costs,
        mortgage=mortgage,
        down_payment=down_payment,
        cash_needed=down_payment + costs,
    )


def max_loan(payment: Decimal, annual_rate: Decimal, months: int) -> Decimal:
    """The capital a monthly `payment` repays in `months` (Excel's VA)."""
    if payment <= 0 or months <= 0:
        return _ZERO
    rate = monthly_rate(annual_rate)
    if rate == 0:
        return round_cents(payment * months)
    return round_cents(payment * (_ONE - (_ONE + rate) ** -months) / rate)


@dataclass(frozen=True)
class Affordability:
    payment: Decimal
    debt_ratio: Decimal | None  # percent of net income going to debts, this one included
    max_payment: Decimal
    max_price: Decimal | None  # None: no limit from the data given
    limited_by: Literal["income", "savings"] | None
    months_to_buy: int | None  # 0: affordable now; None: not at this saving pace


def affordability(
    price: Decimal,
    tax: PurchaseTax,
    fees: Fees,
    financed_percent: Decimal,
    *,
    annual_rate: Decimal,
    months: int,
    net_income: Decimal,
    other_debts: Decimal,
    max_ratio: Decimal,
    savings: Decimal | None,
    monthly_saving: Decimal,
) -> Affordability:
    bought = purchase(price, tax, fees, financed_percent)
    payment = french_payment(bought.mortgage, annual_rate, months) if bought.mortgage else _ZERO
    ratio = (
        ((payment + other_debts) * _HUNDRED / net_income).quantize(Decimal("0.1"))
        if net_income > 0
        else None
    )
    max_payment = max(round_cents(net_income * max_ratio / _HUNDRED) - other_debts, _ZERO)

    limits: list[tuple[Decimal, Literal["income", "savings"]]] = []
    if net_income > 0 and financed_percent > 0:
        by_income = max_loan(max_payment, annual_rate, months) * _HUNDRED / financed_percent
        limits.append((by_income, "income"))
    if savings is not None:
        limits.append((_max_price_for(savings, tax, fees, financed_percent), "savings"))
    best = min(limits) if limits else None

    if savings is None:
        to_buy = None
    elif savings >= bought.cash_needed:
        to_buy = 0
    elif monthly_saving > 0:
        missing = bought.cash_needed - savings
        to_buy = int((missing / monthly_saving).to_integral_value(rounding=ROUND_CEILING))
    else:
        to_buy = None
    return Affordability(
        payment=payment,
        debt_ratio=ratio,
        max_payment=max_payment,
        max_price=best[0].to_integral_value(rounding=ROUND_FLOOR) if best else None,
        limited_by=best[1] if best else None,
        months_to_buy=to_buy,
    )


def _max_price_for(savings: Decimal, tax: PurchaseTax, fees: Fees, financed: Decimal) -> Decimal:
    """The highest price whose down payment and costs fit in `savings` (to the euro)."""
    low, high = _ZERO, _MAX_PRICE
    if purchase(high, tax, fees, financed).cash_needed <= savings:
        return high
    while high - low > _ONE:
        middle = ((low + high) / 2).to_integral_value(rounding=ROUND_FLOOR)
        if purchase(middle, tax, fees, financed).cash_needed <= savings:
            low = middle
        else:
            high = middle
    return low

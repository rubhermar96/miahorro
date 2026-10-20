"""Personal loans and the real cost of credit (RF-CAL-09).

The TAE follows the official formula of Ley 16/2011 (Anexo I), the one banks must use: the
annual rate X that makes what the borrower receives equal to what they pay back, each
amount discounted to the day of the loan,

    Σ disbursed_k · (1 + X)^(-t_k) = Σ paid_l · (1 + X)^(-s_l)

with times in years and each month counted as 1/12 of a year.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from finance.loans import french_payment, monthly_rate
from finance.money import round_cents

_ZERO = Decimal(0)
_ONE = Decimal(1)
_HUNDRED = Decimal(100)
_TOLERANCE = Decimal("1e-10")


def _present_value(flows: Sequence[tuple[int, Decimal]], rate: Decimal) -> Decimal:
    month = (_ONE + rate) ** (-_ONE / 12)  # discount for one month: 1/12 of a year
    return sum((amount * month**number for number, amount in flows), _ZERO)


def apr(received: Decimal, payments: Sequence[tuple[int, Decimal]]) -> Decimal | None:
    """TAE in percent (two decimals) of receiving `received` today and paying back `payments`
    as (months from today, amount). None if it cannot be computed (nothing is paid back, or
    less than what was received)."""
    if received <= 0 or not payments:
        return None
    if sum((amount for _, amount in payments), _ZERO) < received:
        return None
    # The present value falls as the rate rises: bisect between 0 % and 1.000 %.
    low, high = _ZERO, Decimal(10)
    if _present_value(payments, high) > received:
        return None
    while high - low > _TOLERANCE:
        middle = (low + high) / 2
        if _present_value(payments, middle) > received:
            low = middle
        else:
            high = middle
    return ((low + high) / 2 * _HUNDRED).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class PersonalLoan:
    payment: Decimal  # instalment, without the linked costs
    monthly_total: Decimal  # instalment plus monthly costs (insurance…)
    interest: Decimal
    fees: Decimal  # opening fee and other upfront costs
    extras: Decimal  # monthly costs over the whole term
    total_cost: Decimal  # interest + fees + extras: what the money costs
    total_paid: Decimal  # everything paid, capital included
    apr: Decimal | None  # TAE, percent


def personal_loan(
    amount: Decimal,
    tin: Decimal,
    months: int,
    *,
    opening_fee_percent: Decimal = _ZERO,
    upfront_costs: Decimal = _ZERO,
    monthly_costs: Decimal = _ZERO,
) -> PersonalLoan:
    """A French loan: its instalment, what it costs in total and its real TAE.

    The opening fee and the upfront costs are paid at the start (the borrower receives less);
    monthly costs, such as a linked insurance, are paid with every instalment.
    """
    payment = french_payment(amount, tin, months)
    # Interest month by month, rounded like the bank does; the last instalment absorbs it.
    outstanding = amount
    interest = _ZERO
    rate = monthly_rate(tin)
    for number in range(1, months + 1):
        month_interest = round_cents(outstanding * rate)
        repaid = outstanding if number == months else min(payment - month_interest, outstanding)
        interest += month_interest
        outstanding -= repaid
    fees = round_cents(amount * opening_fee_percent / _HUNDRED) + upfront_costs
    extras = monthly_costs * months
    last = amount + interest - payment * (months - 1)
    flows = [(k, (payment if k < months else last) + monthly_costs) for k in range(1, months + 1)]
    return PersonalLoan(
        payment=payment,
        monthly_total=payment + monthly_costs,
        interest=interest,
        fees=fees,
        extras=extras,
        total_cost=interest + fees + extras,
        total_paid=amount + interest + fees + extras,
        apr=apr(amount - fees, flows),
    )

"""Buying a car (RF-CAL-07): paying cash, a loan, dealer finance with a final instalment
(PCP, "multiopción") or renting, compared by the total cost of owning the car, per year and
per km.

Each option is costed over its own horizon: the years of use when the car is yours, the
contract when it is returned (PCP returned, renting). Renting fees include insurance,
maintenance, road tax and ITV; fuel or electricity is always paid by the driver.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from finance.calculators.credit import apr, personal_loan
from finance.loans import monthly_rate
from finance.money import round_cents
from finance.taxes import Bracket, band_rate

type OptionKind = Literal["cash", "loan", "pcp", "renting"]

_ZERO = Decimal(0)
_ONE = Decimal(1)
_HUNDRED = Decimal(100)
_TWELVE = Decimal(12)
CAR_VAT = Decimal(21)
# Resale estimate when none is given: a new car loses about a fifth the first year and some
# 15 % of its value each year after.
FIRST_YEAR_KEEPS = Decimal("0.80")
LATER_YEARS_KEEP = Decimal("0.85")


def registration_tax(price_with_vat: Decimal, co2: int, brackets: Sequence[Bracket]) -> Decimal:
    """Impuesto de matriculación: the CO₂ band's rate on the price without VAT."""
    base = price_with_vat * _HUNDRED / (_HUNDRED + CAR_VAT)
    return round_cents(base * band_rate(Decimal(co2), brackets) / _HUNDRED)


def itv_count(years: Decimal) -> int:
    """ITV inspections of a new car (turismo) in its first `years`: at 4, 6, 8 and 10 years
    old, then every year (Real Decreto 920/2017)."""
    due = [4, 6, 8, 10, *range(11, 61)]
    return sum(1 for age in due if age <= years)


def estimated_resale(price: Decimal, years: Decimal) -> Decimal:
    if years <= 0:
        return price
    return round_cents(price * FIRST_YEAR_KEEPS * LATER_YEARS_KEEP ** (years - 1))


@dataclass(frozen=True)
class Running:
    km_per_year: int
    consumption: Decimal  # litres or kWh per 100 km
    energy_price: Decimal  # € per litre or kWh
    insurance: Decimal  # a year
    road_tax: Decimal  # IVTM, a year
    maintenance: Decimal  # a year
    itv_cost: Decimal  # each inspection


@dataclass(frozen=True)
class RunningCosts:
    energy: Decimal
    insurance: Decimal
    road_tax: Decimal
    maintenance: Decimal
    itv: Decimal

    @property
    def total(self) -> Decimal:
        return self.energy + self.insurance + self.road_tax + self.maintenance + self.itv


def running_costs(running: Running, months: int, *, renting: bool = False) -> RunningCosts:
    years = Decimal(months) / _TWELVE
    energy = round_cents(
        running.km_per_year * years * running.consumption / _HUNDRED * running.energy_price
    )
    if renting:
        return RunningCosts(energy, _ZERO, _ZERO, _ZERO, _ZERO)
    return RunningCosts(
        energy=energy,
        insurance=round_cents(running.insurance * years),
        road_tax=round_cents(running.road_tax * years),
        maintenance=round_cents(running.maintenance * years),
        itv=itv_count(years) * running.itv_cost,
    )


@dataclass(frozen=True)
class CarOption:
    kind: OptionKind
    name: str
    down_payment: Decimal = _ZERO  # entrada; for renting, the initial payment
    rate: Decimal = _ZERO  # TIN
    months: int = 0  # term of the loan, PCP or renting contract
    opening_fee_percent: Decimal = _ZERO
    final_payment: Decimal = _ZERO  # PCP: cuota final (valor futuro garantizado)
    keep: bool = True  # PCP: pay the final instalment and keep the car
    monthly_fee: Decimal = _ZERO  # renting


@dataclass(frozen=True)
class CarOutcome:
    name: str
    kind: OptionKind
    months: int  # horizon the costs cover
    upfront: Decimal
    monthly: Decimal
    final_payment: Decimal
    financing: Decimal  # interest and fees
    running: RunningCosts
    resale: Decimal  # value of the car at the end, which is subtracted
    total: Decimal  # net cost over the horizon
    per_year: Decimal
    per_km: Decimal | None
    apr: Decimal | None


def pcp_payment(financed: Decimal, rate: Decimal, months: int, final: Decimal) -> Decimal:
    """Instalment of a loan that leaves `final` to pay at the end, with the last one."""
    i = monthly_rate(rate)
    if i == 0:
        return round_cents((financed - final) / months)
    discount = (_ONE + i) ** -months
    return round_cents((financed - final * discount) * i / (_ONE - discount))


def cost_option(
    option: CarOption,
    *,
    price: Decimal,
    registration: Decimal,
    years: int,
    running: Running,
    resale: Decimal | None,
) -> CarOutcome:
    """`price` with VAT; `registration` is what is paid on top of it (zero if included)."""
    acquisition = price + registration
    own_months = years * 12
    financed = max(acquisition - option.down_payment, _ZERO)
    fees = round_cents(financed * option.opening_fee_percent / _HUNDRED)
    monthly = final = financing = _ZERO
    rate_apr: Decimal | None = None

    if option.kind == "cash":
        months, upfront, outlay = own_months, acquisition, acquisition
    elif option.kind == "loan":
        loan = personal_loan(financed, option.rate, option.months, upfront_costs=fees)
        months, monthly, rate_apr = own_months, loan.payment, loan.apr
        financing = loan.interest + fees
        upfront = option.down_payment + fees
        outlay = acquisition + financing
    elif option.kind == "pcp":
        monthly = pcp_payment(financed, option.rate, option.months, option.final_payment)
        interest = monthly * option.months + option.final_payment - financed
        financing = interest + fees
        upfront = option.down_payment + fees
        flows = [(k, monthly) for k in range(1, option.months + 1)]
        flows.append((option.months, option.final_payment))
        rate_apr = apr(financed - fees, flows)
        if option.keep:
            months, final = max(own_months, option.months), option.final_payment
            outlay = acquisition + financing
        else:
            months = option.months
            outlay = option.down_payment + fees + monthly * option.months
    else:  # renting
        months, monthly, upfront = option.months, option.monthly_fee, option.down_payment
        outlay = option.down_payment + option.monthly_fee * option.months

    returned = option.kind == "renting" or (option.kind == "pcp" and not option.keep)
    costs = running_costs(running, months, renting=option.kind == "renting")
    horizon_years = Decimal(months) / _TWELVE
    value_left = _ZERO
    if not returned:
        # The resale value given is for the years of use; a longer horizon is estimated.
        given = resale is not None and months == own_months
        value_left = (
            resale if given and resale is not None else estimated_resale(price, horizon_years)
        )
    total = outlay + costs.total - value_left
    km = running.km_per_year * horizon_years
    return CarOutcome(
        name=option.name,
        kind=option.kind,
        months=months,
        upfront=upfront,
        monthly=monthly,
        final_payment=final,
        financing=financing,
        running=costs,
        resale=value_left,
        total=total,
        per_year=round_cents(total / horizon_years) if months else total,
        per_km=(total / km).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP) if km else None,
        apr=rate_apr,
    )

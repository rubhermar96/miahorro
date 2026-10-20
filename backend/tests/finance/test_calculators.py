import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from finance.calculators.car import (
    CarOption,
    Running,
    cost_option,
    estimated_resale,
    itv_count,
    pcp_payment,
    registration_tax,
)
from finance.calculators.credit import apr, personal_loan
from finance.calculators.home import (
    Affordability,
    Fees,
    PurchaseTax,
    affordability,
    max_loan,
    purchase,
)
from finance.calculators.mortgage import Offer, outcome
from finance.calculators.savings import (
    compound,
    emergency_fund,
    months_to_target,
    required_monthly,
)
from finance.loans import french_payment
from finance.money import round_cents
from finance.taxes import Bracket
from tests.finance.test_taxes import CO2, SAVINGS

START = dt.date(2026, 11, 1)

# --- Compound interest ------------------------------------------------------------------------


def test_compound_monthly_matches_yearly_compounding() -> None:
    # 10.000 € at 5 % for 10 years: 10.000 * 1,05^10 = 16.288,95
    result = compound(Decimal(10000), Decimal(0), Decimal(5), 10)

    assert result.final == Decimal("16288.95")
    assert result.years[0].balance == Decimal("10500.00")
    assert result.contributed == Decimal("10000.00")
    assert result.gains == Decimal("6288.95")
    assert result.tax == 0


def test_compound_real_value_discounts_inflation() -> None:
    result = compound(Decimal(10000), Decimal(0), Decimal(5), 10, inflation=Decimal(2))

    expected = Decimal(10000) * Decimal("1.05") ** 10 / Decimal("1.02") ** 10
    assert result.final_real == round_cents(expected)
    assert result.final_real < result.final


def test_compound_taxes_gains_at_the_end_by_tranches() -> None:
    result = compound(Decimal(10000), Decimal(0), Decimal(5), 10, tax_mode="end", brackets=SAVINGS)

    # 6.288,95 of gains: 6.000 * 19 % + 288,95 * 21 % = 1.200,68
    assert result.tax == Decimal("1200.68")
    assert result.final == Decimal("15088.27")


def test_compound_taxes_each_year_like_a_deposit() -> None:
    result = compound(
        Decimal(10000), Decimal(0), Decimal(5), 10, tax_mode="yearly", brackets=SAVINGS
    )

    # Every year's gain is under 6.000 €: 19 % of it goes, so it grows 4,05 % a year.
    assert result.final == round_cents(Decimal(10000) * Decimal("1.0405") ** 10)
    assert result.years[0].tax == Decimal("95.00")


def test_compound_contributions_grow_each_year() -> None:
    flat = compound(Decimal(0), Decimal(100), Decimal(0), 2)
    growing = compound(Decimal(0), Decimal(100), Decimal(0), 2, yearly_increase=Decimal(10))

    assert flat.final == Decimal("2400.00")
    assert growing.final == Decimal("2520.00")  # 1.200 + 12 * 110


def test_compound_contributions_go_in_at_the_start_of_the_month() -> None:
    # 100 € a month at 12,6825 % (1 % a month): the first one earns a whole month.
    result = compound(Decimal(0), Decimal(100), Decimal("12.6825"), 1)

    assert result.final == Decimal("1280.93")


# --- Savings target ---------------------------------------------------------------------------


def test_required_monthly_without_returns() -> None:
    assert required_monthly(Decimal(12000), Decimal(0), 24, Decimal(0)) == Decimal("500.00")
    assert required_monthly(Decimal(10000), Decimal(0), 12, Decimal(0)) == Decimal("833.34")
    assert required_monthly(Decimal(5000), Decimal(6000), 12, Decimal(0)) == 0


def test_required_monthly_counts_returns() -> None:
    with_returns = required_monthly(Decimal(20000), Decimal(2000), 36, Decimal(4))
    assert with_returns < required_monthly(Decimal(20000), Decimal(2000), 36, Decimal(0))


def test_months_to_target() -> None:
    assert months_to_target(Decimal(1000), Decimal(0), Decimal(100), Decimal(0)) == 10
    assert months_to_target(Decimal(1000), Decimal(1000), Decimal(0), Decimal(0)) == 0
    assert months_to_target(Decimal(1000), Decimal(0), Decimal(0), Decimal(0)) is None


@settings(max_examples=60, deadline=None)
@given(
    target=st.integers(min_value=1000, max_value=200000),
    initial=st.integers(min_value=0, max_value=5000),
    months=st.integers(min_value=1, max_value=240),
    rate=st.decimals(min_value=0, max_value=10, places=2),
)
def test_saving_the_required_amount_reaches_the_target_on_time(
    target: int, initial: int, months: int, rate: Decimal
) -> None:
    monthly = required_monthly(Decimal(target), Decimal(initial), months, rate)
    reached = months_to_target(Decimal(target), Decimal(initial), monthly, rate)
    assert reached is not None
    assert reached <= months


# --- Emergency fund ---------------------------------------------------------------------------


def test_emergency_fund() -> None:
    fund = emergency_fund(Decimal(1500), 6, Decimal(4000), Decimal(500))

    assert fund.target == Decimal("9000.00")
    assert fund.covered_months == Decimal("2.7")
    assert fund.missing == Decimal("5000.00")
    assert fund.months_to_complete == 10


def test_emergency_fund_already_complete() -> None:
    fund = emergency_fund(Decimal(1000), 3, Decimal(5000), Decimal(0))

    assert fund.missing == 0
    assert fund.months_to_complete is None
    assert fund.covered_months == Decimal("5.0")


# --- TAE and personal loans -------------------------------------------------------------------


def _float_tae(received: float, payment: float, months: int) -> float:
    """Independent check: bisection on floats with the formula of Ley 16/2011."""
    low, high = 0.0, 1.0
    for _ in range(200):
        mid = (low + high) / 2
        value = sum(payment / (1 + mid) ** (k / 12) for k in range(1, months + 1))
        low, high = (mid, high) if value > received else (low, mid)
    return round(low * 100, 2)


def test_tae_without_fees_is_the_effective_rate() -> None:
    loan = personal_loan(Decimal(10000), Decimal(7), 60)

    # (1 + 7 %/12)^12 - 1 = 7,229 %
    assert loan.apr == Decimal("7.23")
    assert loan.payment == Decimal("198.01")  # =PAGO(7%/12; 60; -10000)


def test_tae_with_an_opening_fee_matches_the_official_formula() -> None:
    loan = personal_loan(Decimal(6000), Decimal("9.95"), 36, opening_fee_percent=Decimal(2))

    assert loan.fees == Decimal("120.00")
    expected = _float_tae(6000 - 120, float(loan.payment), 36)
    assert loan.apr is not None
    assert abs(float(loan.apr) - expected) <= 0.01
    assert loan.apr > Decimal("10.42")  # above the TIN's own effective rate


def test_zero_percent_tin_with_fees_is_not_free() -> None:
    loan = personal_loan(Decimal(1200), Decimal(0), 12, opening_fee_percent=Decimal(3))

    assert loan.interest == 0
    assert loan.total_cost == Decimal("36.00")
    assert loan.apr is not None
    assert loan.apr > Decimal(5)


def test_loan_totals_add_up() -> None:
    loan = personal_loan(
        Decimal(10000), Decimal(6), 48, upfront_costs=Decimal(50), monthly_costs=Decimal(10)
    )

    assert loan.monthly_total == loan.payment + 10
    assert loan.total_cost == loan.interest + Decimal(50) + Decimal(480)
    assert loan.total_paid == Decimal(10000) + loan.total_cost


def test_apr_edge_cases() -> None:
    assert apr(Decimal(0), [(1, Decimal(10))]) is None
    assert apr(Decimal(100), []) is None
    assert apr(Decimal(100), [(1, Decimal(50))]) is None  # pays back less than received
    assert apr(Decimal(100), [(12, Decimal(100))]) == Decimal("0.00")


# --- Mortgage ---------------------------------------------------------------------------------


def test_fixed_mortgage_with_and_without_discount() -> None:
    offer = Offer(
        "Fija",
        "fixed",
        Decimal(5),
        discount=Decimal("0.5"),
        linked_yearly_cost=Decimal(300),
    )
    plain = outcome(Decimal(150000), 360, offer, Decimal(2), discounted=False, start=START)
    linked = outcome(Decimal(150000), 360, offer, Decimal(2), discounted=True, start=START)

    assert plain.first_payment == Decimal("805.23")
    assert plain.later_payment is None
    assert plain.linked_cost == 0
    assert linked.first_payment == Decimal("760.03")  # =PAGO(4,5%/12; 360; -150000)
    assert linked.linked_cost == Decimal("9000.00")
    assert linked.interest < plain.interest
    assert len(plain.years) == 30
    assert plain.years[-1].outstanding == 0
    assert sum(y.principal for y in plain.years) == Decimal(150000)


def test_mixed_mortgage_depends_on_the_euribor_after_the_fixed_years() -> None:
    offer = Offer("Mixta", "mixed", Decimal(2), fixed_months=120, spread=Decimal("0.8"))
    low = outcome(Decimal(200000), 300, offer, Decimal(1), discounted=False, start=START)
    high = outcome(Decimal(200000), 300, offer, Decimal(4), discounted=False, start=START)

    assert (
        low.first_payment == high.first_payment == french_payment(Decimal(200000), Decimal(2), 300)
    )
    assert low.later_payment is not None
    assert high.later_payment is not None
    assert high.later_payment > low.later_payment
    assert high.total_cost > low.total_cost


def test_variable_rate_never_goes_below_zero() -> None:
    offer = Offer("Variable", "variable", Decimal(1), fixed_months=12, discount=Decimal(1))
    result = outcome(Decimal(12000), 24, offer, Decimal(0), discounted=True, start=START)

    assert result.interest == 0


# --- Home purchase ----------------------------------------------------------------------------

FEES = Fees(
    notary=Decimal(700), registry=Decimal(450), gestoria=Decimal(350), appraisal=Decimal(400)
)
MADRID = PurchaseTax([Bracket(None, Decimal(6))])


def test_second_hand_home_in_madrid() -> None:
    bought = purchase(Decimal(200000), MADRID, FEES, Decimal(80))

    assert bought.tax == Decimal("12000.00")
    assert bought.ajd == 0
    assert bought.costs == Decimal("13900.00")
    assert bought.mortgage == Decimal("160000.00")
    assert bought.down_payment == Decimal("40000.00")
    assert bought.cash_needed == Decimal("53900.00")


def test_new_home_pays_vat_and_ajd() -> None:
    andalucia = PurchaseTax([Bracket(None, Decimal(10))], marginal=False, ajd=Decimal("1.2"))
    bought = purchase(Decimal(200000), andalucia, FEES, Decimal(80))

    assert (bought.tax, bought.ajd) == (Decimal("20000.00"), Decimal("2400.00"))


def test_progressive_itp_in_cataluna() -> None:
    cataluna = PurchaseTax(
        [
            Bracket(Decimal(600000), Decimal(10)),
            Bracket(Decimal(900000), Decimal(11)),
            Bracket(Decimal(1500000), Decimal(12)),
            Bracket(None, Decimal(13)),
        ]
    )
    assert purchase(Decimal(700000), cataluna, FEES, Decimal(0)).tax == Decimal("71000.00")


def test_cash_purchase_has_no_appraisal() -> None:
    bought = purchase(Decimal(100000), MADRID, FEES, Decimal(0))

    assert bought.mortgage == 0
    assert bought.appraisal == 0
    assert bought.cash_needed == Decimal(100000) + Decimal(6000) + Decimal(1500)


def test_max_loan_is_the_inverse_of_the_payment() -> None:
    assert abs(max_loan(Decimal("805.23"), Decimal(5), 360) - Decimal(150000)) < 1
    assert max_loan(Decimal(500), Decimal(0), 100) == Decimal("50000.00")
    assert max_loan(Decimal(0), Decimal(3), 100) == 0


def _afford(**overrides: Any) -> Affordability:
    values: dict[str, Any] = {
        "annual_rate": Decimal(3),
        "months": 360,
        "net_income": Decimal(3000),
        "other_debts": Decimal(0),
        "max_ratio": Decimal(35),
        "savings": Decimal(100000),
        "monthly_saving": Decimal(1000),
    }
    values.update(overrides)
    return affordability(Decimal(200000), MADRID, FEES, Decimal(80), **values)


def test_affordability_limited_by_income() -> None:
    result = _afford()

    assert result.payment == french_payment(Decimal(160000), Decimal(3), 360)
    assert result.debt_ratio == (result.payment * 100 / 3000).quantize(Decimal("0.1"))
    assert result.max_payment == Decimal("1050.00")
    assert result.limited_by == "income"
    by_income = max_loan(Decimal(1050), Decimal(3), 360) / Decimal("0.8")
    assert result.max_price == by_income.to_integral_value(rounding="ROUND_FLOOR")
    assert result.months_to_buy == 0


def test_affordability_limited_by_savings() -> None:
    result = _afford(savings=Decimal(50000))

    # 20 % down + 6 % ITP + 1.900 € of costs = 0,26 * price + 1.900 ≤ 50.000
    assert result.limited_by == "savings"
    assert result.max_price == Decimal(185000)


def test_when_the_purchase_is_affordable_at_this_saving_pace() -> None:
    assert _afford(savings=Decimal(20000)).months_to_buy == 34  # 33.900 € missing
    assert _afford(savings=Decimal(20000), monthly_saving=Decimal(0)).months_to_buy is None
    assert _afford(savings=None).max_price is not None


def test_other_debts_reduce_what_can_be_borrowed() -> None:
    assert _afford(other_debts=Decimal(300)).max_payment == Decimal("750.00")
    assert _afford(net_income=Decimal(0)).debt_ratio is None


# --- Car --------------------------------------------------------------------------------------

RUNNING = Running(
    km_per_year=15000,
    consumption=Decimal(6),
    energy_price=Decimal("1.6"),
    insurance=Decimal(500),
    road_tax=Decimal(100),
    maintenance=Decimal(300),
    itv_cost=Decimal(45),
)


def test_registration_tax_on_the_price_without_vat() -> None:
    assert registration_tax(Decimal(24200), 130, CO2) == Decimal("950.00")
    assert registration_tax(Decimal(24200), 110, CO2) == 0


@pytest.mark.parametrize(("years", "count"), [(3, 0), (4, 1), (5, 1), (10, 4), (12, 6)])
def test_itv_inspections_of_a_new_car(years: int, count: int) -> None:
    assert itv_count(Decimal(years)) == count


def test_resale_estimate_falls_every_year() -> None:
    assert estimated_resale(Decimal(20000), Decimal(1)) == Decimal("16000.00")
    assert estimated_resale(Decimal(20000), Decimal(2)) == Decimal("13600.00")


def test_cash_purchase_cost_of_ownership() -> None:
    result = cost_option(
        CarOption("cash", "Contado"),
        price=Decimal(20000),
        registration=Decimal(0),
        years=5,
        running=RUNNING,
        resale=Decimal(9000),
    )

    # 1.440 €/year of fuel, 500 + 100 + 300 a year and one ITV at 4 years
    assert result.running.total == Decimal("11745.00")
    assert result.total == Decimal("22745.00")
    assert result.per_year == Decimal("4549.00")
    assert result.per_km == Decimal("0.303")


def test_loan_adds_interest_and_fees() -> None:
    cash = cost_option(
        CarOption("cash", "Contado"),
        price=Decimal(20000),
        registration=Decimal(500),
        years=5,
        running=RUNNING,
        resale=Decimal(9000),
    )
    loan = cost_option(
        CarOption(
            "loan",
            "Préstamo",
            down_payment=Decimal(5000),
            rate=Decimal(7),
            months=60,
            opening_fee_percent=Decimal(2),
        ),
        price=Decimal(20000),
        registration=Decimal(500),
        years=5,
        running=RUNNING,
        resale=Decimal(9000),
    )

    expected = personal_loan(Decimal(15500), Decimal(7), 60)
    assert loan.monthly == expected.payment
    assert loan.financing == expected.interest + Decimal("310.00")
    assert loan.total == cash.total + loan.financing
    assert loan.apr is not None
    assert loan.apr > Decimal(7)


def test_pcp_keeping_or_returning_the_car() -> None:
    option = CarOption(
        "pcp",
        "Multiopción",
        down_payment=Decimal(4000),
        rate=Decimal(6),
        months=36,
        final_payment=Decimal(8000),
    )
    common = {
        "price": Decimal(20000),
        "registration": Decimal(0),
        "years": 3,
        "running": RUNNING,
        "resale": Decimal(11000),
    }
    keep = cost_option(option, **common)  # type: ignore[arg-type]
    give_back = cost_option(
        CarOption(**{**option.__dict__, "keep": False}),
        **common,  # type: ignore[arg-type]
    )

    assert keep.monthly == pcp_payment(Decimal(16000), Decimal(6), 36, Decimal(8000))
    assert keep.final_payment == Decimal(8000)
    assert keep.resale == Decimal(11000)
    assert keep.financing > 0
    assert give_back.resale == 0
    assert give_back.total == Decimal(4000) + keep.monthly * 36 + give_back.running.total
    assert keep.apr is not None
    assert keep.apr > Decimal(6)


def test_pcp_without_interest_splits_the_rest_evenly() -> None:
    assert pcp_payment(Decimal(16000), Decimal(0), 32, Decimal(8000)) == Decimal("250.00")


def test_renting_only_adds_fuel() -> None:
    result = cost_option(
        CarOption("renting", "Renting", monthly_fee=Decimal(350), months=48),
        price=Decimal(20000),
        registration=Decimal(0),
        years=5,
        running=RUNNING,
        resale=None,
    )

    assert result.months == 48
    assert result.running.total == Decimal("5760.00")  # 4 years of fuel
    assert result.total == Decimal("22560.00")
    assert result.per_year == Decimal("5640.00")
    assert result.resale == 0

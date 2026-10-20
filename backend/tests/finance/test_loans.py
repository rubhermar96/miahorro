import datetime as dt
from decimal import Decimal

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from finance.loans import (
    Prepayment,
    add_months,
    early_repayment_fee,
    french_payment,
    legal_fee_cap,
    months_to_repay,
    schedule,
)

START = dt.date(2026, 11, 5)


def fixed(rate: str):  # type: ignore[no-untyped-def]
    return lambda number, date: Decimal(rate)


def test_french_payment_matches_excel_pago() -> None:
    # =PAGO(5%/12; 360; -150000) → 805,23
    assert french_payment(Decimal(150000), Decimal(5), 360) == Decimal("805.23")
    # =PAGO(3,5%/12; 240; -200000) → 1.159,92
    assert french_payment(Decimal(200000), Decimal("3.5"), 240) == Decimal("1159.92")
    assert french_payment(Decimal(1200), Decimal(0), 12) == Decimal("100.00")


def test_first_interest_matches_excel_pagoint() -> None:
    rows = schedule(Decimal(150000), START, 360, fixed("5"))

    # =PAGOINT(5%/12; 1; 360; -150000) → 625,00
    assert (rows[0].interest, rows[0].principal) == (Decimal("625.00"), Decimal("180.23"))
    assert len(rows) == 360
    assert rows[-1].outstanding == 0
    # The exact instalment is 805,2324…: the cents rounded away add up in the last one.
    assert rows[-1].payment == Decimal("807.70")


def test_months_to_repay_matches_excel_nper() -> None:
    # =NPER(5%/12; -805,23; 150000) → 360,0025: the sliver goes into the last instalment
    assert months_to_repay(Decimal(150000), Decimal(5), Decimal("805.23")) == 360
    assert months_to_repay(Decimal(1200), Decimal(0), Decimal(100)) == 12
    with pytest.raises(ValueError, match="no cubre los intereses"):
        months_to_repay(Decimal(100000), Decimal(12), Decimal(500))


def test_linear_repays_the_same_capital_every_month() -> None:
    rows = schedule(Decimal(12000), START, 12, fixed("6"), system="linear")

    assert {row.principal for row in rows} == {Decimal("1000.00")}
    assert (rows[0].interest, rows[-1].interest) == (Decimal("60.00"), Decimal("5.00"))
    assert rows[0].payment > rows[-1].payment


def test_grace_months_pay_only_interest() -> None:
    rows = schedule(Decimal(10000), START, 12, fixed("6"), grace_months=3)

    assert [(r.payment, r.principal) for r in rows[:3]] == [(Decimal("50.00"), Decimal(0))] * 3
    # Then a French instalment over the 9 months left.
    assert rows[3].payment == french_payment(Decimal(10000), Decimal(6), 9)
    assert rows[-1].outstanding == 0
    assert len(rows) == 12


def test_zero_rate() -> None:
    rows = schedule(Decimal("1000.00"), START, 3, fixed("0"))

    assert [r.principal for r in rows] == [Decimal("333.33"), Decimal("333.33"), Decimal("333.34")]
    assert sum(r.interest for r in rows) == 0


def test_a_rate_change_recomputes_the_instalment() -> None:
    def euribor(number: int, date: dt.date) -> Decimal:
        return Decimal(3) if number <= 12 else Decimal(4)

    rows = schedule(Decimal(100000), START, 120, euribor)

    assert rows[0].payment == french_payment(Decimal(100000), Decimal(3), 120)
    assert rows[12].payment == french_payment(rows[11].outstanding, Decimal(4), 108)
    assert rows[-1].outstanding == 0
    assert len(rows) == 120


def test_early_repayment_reducing_the_instalment() -> None:
    plain = schedule(Decimal(100000), START, 120, fixed("3"))
    early = [Prepayment(dt.date(2027, 6, 1), Decimal(20000), "reduce_payment")]

    rows = schedule(Decimal(100000), START, 120, fixed("3"), prepayments=early)

    assert len(rows) == 120  # same term
    assert rows[8].date == dt.date(2027, 7, 5)
    assert rows[8].payment < plain[8].payment
    assert sum(r.interest for r in rows) < sum(r.interest for r in plain)
    assert sum(r.principal for r in rows) == Decimal(80000)


def test_early_repayment_reducing_the_term() -> None:
    plain = schedule(Decimal(100000), START, 120, fixed("3"))
    early = [Prepayment(dt.date(2027, 6, 1), Decimal(20000), "reduce_term")]

    rows = schedule(Decimal(100000), START, 120, fixed("3"), prepayments=early)

    assert len(rows) < 120  # fewer instalments
    assert rows[8].payment == plain[8].payment  # the same instalment
    assert rows[-1].outstanding == 0
    # Reducing the term saves more interest than reducing the instalment.
    reduced = schedule(
        Decimal(100000),
        START,
        120,
        fixed("3"),
        prepayments=[Prepayment(dt.date(2027, 6, 1), Decimal(20000), "reduce_payment")],
    )
    assert sum(r.interest for r in rows) < sum(r.interest for r in reduced)


def test_repaying_everything_early_ends_the_loan() -> None:
    rows = schedule(
        Decimal(5000),
        START,
        24,
        fixed("5"),
        prepayments=[Prepayment(dt.date(2027, 3, 1), Decimal(99999), "reduce_term")],
    )

    assert len(rows) == 4  # November to February


@settings(max_examples=200, deadline=None)
@given(
    principal=st.decimals(min_value=Decimal(100), max_value=Decimal(1_000_000), places=2),
    rate=st.decimals(min_value=Decimal(0), max_value=Decimal(12), places=3),
    months=st.integers(min_value=1, max_value=480),
    system=st.sampled_from(["french", "linear"]),
    grace=st.integers(min_value=0, max_value=12),
)
def test_capital_repaid_equals_the_loan(
    principal: Decimal, rate: Decimal, months: int, system: str, grace: int
) -> None:
    grace = min(grace, months - 1)
    assume(principal / months >= 5)  # realistic instalments: cents cannot add up to a month
    rows = schedule(principal, START, months, fixed(str(rate)), system=system, grace_months=grace)  # type: ignore[arg-type]

    assert sum(r.principal for r in rows) == principal
    assert rows[-1].outstanding == 0
    assert len(rows) == months
    assert all(r.payment == r.interest + r.principal for r in rows)
    assert all(r.principal >= 0 for r in rows)


def test_dates_keep_the_payment_day() -> None:
    assert add_months(dt.date(2026, 1, 31), 1, 31) == dt.date(2026, 2, 28)
    assert add_months(dt.date(2026, 1, 31), 2, 31) == dt.date(2026, 3, 31)
    rows = schedule(Decimal(3000), dt.date(2026, 1, 31), 3, fixed("0"))
    assert [r.date for r in rows] == [
        dt.date(2026, 1, 31),
        dt.date(2026, 2, 28),
        dt.date(2026, 3, 31),
    ]


@pytest.mark.parametrize(
    ("kind", "rate_type", "years", "months_left", "expected"),
    [
        ("mortgage", "fixed", 4, 200, Decimal(2)),
        ("mortgage", "fixed", 12, 100, Decimal("1.5")),
        ("mortgage", "variable", 2, 200, Decimal("0.25")),
        ("mortgage", "variable", 4, 200, Decimal("0.15")),
        ("mortgage", "variable", 6, 200, Decimal(0)),
        ("personal", "fixed", 1, 30, Decimal(1)),
        ("car", "fixed", 4, 10, Decimal("0.5")),
        ("p2p_owe", "fixed", 1, 10, None),
    ],
)
def test_legal_fee_caps(
    kind: str, rate_type: str, years: int, months_left: int, expected: Decimal | None
) -> None:
    signed = dt.date(2020, 1, 1)
    on = dt.date(2020 + years, 1, 2)

    assert legal_fee_cap(kind, rate_type, signed, on, months_left) == expected


def test_mixed_mortgage_follows_the_fixed_rule_in_its_fixed_period() -> None:
    signed = dt.date(2024, 1, 1)
    cap = legal_fee_cap(
        "mortgage", "mixed", signed, dt.date(2026, 1, 1), 300, fixed_until=dt.date(2029, 1, 1)
    )
    assert cap == Decimal(2)


def test_fee_is_the_contract_one_up_to_the_cap() -> None:
    assert early_repayment_fee(Decimal(10000), Decimal(1), Decimal("0.25")) == Decimal("25.00")
    assert early_repayment_fee(Decimal(10000), Decimal("0.1"), Decimal("0.25")) == Decimal("10.00")
    assert early_repayment_fee(Decimal(10000), Decimal(3), None) == Decimal("300.00")

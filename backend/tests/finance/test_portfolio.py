import datetime as dt
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from finance.isin import is_valid_isin, normalize_isin
from finance.portfolio import (
    Operation,
    PortfolioError,
    replay,
    repurchase_window,
    repurchased,
)

D = Decimal


def buy(id_: str, date: str, units: str, amount: str, fee: str = "0", inv: str = "A") -> Operation:
    return Operation(id_, inv, dt.date.fromisoformat(date), "buy", D(units), D(amount), D(fee))


def sell(id_: str, date: str, units: str, amount: str, fee: str = "0", inv: str = "A") -> Operation:
    return Operation(id_, inv, dt.date.fromisoformat(date), "sell", D(units), D(amount), D(fee))


# --- ISIN -------------------------------------------------------------------------------------


@pytest.mark.parametrize("code", ["US0378331005", "ES0113900J37", "IE00B4L5Y983"])
def test_valid_isins(code: str) -> None:
    assert is_valid_isin(code)


@pytest.mark.parametrize("code", ["US0378331006", "ES0113900J3", "es0113900J37", "1234567890AB"])
def test_invalid_isins(code: str) -> None:
    assert not is_valid_isin(code)


def test_isin_is_tidied_before_checking() -> None:
    assert normalize_isin(" es01 1390 0j37 ") == "ES0113900J37"


# --- FIFO -------------------------------------------------------------------------------------


def test_a_partial_sale_takes_the_oldest_lots_first() -> None:
    holdings = replay(
        [
            buy("b1", "2026-01-10", "10", "1000", fee="1"),
            buy("b2", "2026-02-10", "10", "1200", fee="1"),
            sell("s1", "2026-03-10", "15", "1950", fee="2"),
        ]
    )
    a = holdings["A"]

    first, second = a.disposals
    assert (first.acquired, first.units, first.cost) == (dt.date(2026, 1, 10), D(10), D(1001))
    assert (second.acquired, second.units, second.cost) == (dt.date(2026, 2, 10), D(5), D("600.5"))
    # 1.950 - 2 of fee, shared by units: two thirds and one third
    assert first.proceeds + second.proceeds == 1948
    assert first.gain + second.gain == D("346.5")
    assert (a.units, a.cost) == (D(5), D("600.5"))


def test_the_order_of_a_day_is_kept() -> None:
    holdings = replay([buy("b1", "2026-01-10", "10", "100"), sell("s1", "2026-01-10", "10", "120")])

    assert holdings["A"].units == 0
    assert holdings["A"].disposals[0].gain == 20


def test_selling_more_than_held_is_refused() -> None:
    with pytest.raises(PortfolioError) as error:
        replay([buy("b1", "2026-01-10", "10", "100"), sell("s1", "2026-01-11", "11", "120")])

    assert error.value.operation.id == "s1"
    assert error.value.held == 10


def test_a_sale_before_the_purchase_is_refused() -> None:
    with pytest.raises(PortfolioError):
        replay([sell("s1", "2026-01-09", "1", "12"), buy("b1", "2026-01-10", "10", "100")])


def test_a_transfer_keeps_dates_and_costs() -> None:
    holdings = replay(
        [
            buy("b1", "2020-01-10", "10", "1000"),
            buy("b2", "2021-05-05", "10", "1500"),
            buy("c1", "2024-03-01", "4", "600", inv="B"),
            Operation(
                "t1",
                "A",
                dt.date(2025, 6, 1),
                "transfer",
                units=D(15),
                amount=D(2600),
                target="B",
                target_units=D(30),
            ),
            sell("s1", "2026-01-15", "25", "4000", inv="B"),
        ]
    )
    a, b = holdings["A"], holdings["B"]

    assert (a.units, a.cost) == (D(5), D(750))
    assert a.disposals == []  # a transfer is not a sale
    first, second = b.disposals
    assert (first.acquired, first.units, first.cost) == (dt.date(2020, 1, 10), D(20), D(1000))
    assert (second.acquired, second.units, second.cost) == (dt.date(2021, 5, 5), D(5), D(375))
    # What is left in B: the rest of the 2021 lot and the fund's own 2024 purchase
    assert [(lot.acquired.year, lot.units, lot.cost) for lot in b.lots] == [
        (2021, D(5), D(375)),
        (2024, D(4), D(600)),
    ]


def test_a_split_multiplies_units_and_keeps_the_cost() -> None:
    holdings = replay(
        [
            buy("b1", "2026-01-10", "10", "1000"),
            Operation("x1", "A", dt.date(2026, 2, 1), "split", ratio=D(2)),
            sell("s1", "2026-03-01", "5", "300"),
        ]
    )
    a = holdings["A"]

    assert a.disposals[0].cost == 250
    assert (a.units, a.cost) == (D(15), D(750))


def test_dividends_fees_and_withholdings_are_kept_apart() -> None:
    dividend = Operation(
        "d1", "A", dt.date(2026, 3, 1), "dividend", amount=D(50), withholding=D("9.5")
    )
    fee = Operation("f1", "A", dt.date(2026, 4, 1), "fee", amount=D(12))
    holdings = replay([buy("b1", "2026-01-10", "10", "1000"), dividend, fee])

    a = holdings["A"]
    assert (a.dividends, a.fees, a.cost) == ([dividend], [fee], D(1000))


@settings(max_examples=80, deadline=None)
@given(
    st.lists(
        st.tuples(
            st.integers(min_value=1, max_value=400),  # day
            st.integers(min_value=1, max_value=50),  # units bought
            st.integers(min_value=1, max_value=5000),  # paid
            st.integers(min_value=0, max_value=60),  # % of what is held then sold
        ),
        min_size=1,
        max_size=12,
    )
)
def test_units_and_costs_are_never_lost(steps: list[tuple[int, int, int, int]]) -> None:
    ops: list[Operation] = []
    held = D(0)
    start = dt.date(2025, 1, 1)
    for index, (day, units, paid, share) in enumerate(sorted(steps)):
        date = start + dt.timedelta(days=day)
        ops.append(Operation(f"b{index}", "A", date, "buy", D(units), D(paid)))
        held += units
        sold = (held * share / 100).quantize(D("0.001"))
        if sold > 0:
            ops.append(Operation(f"s{index}", "A", date, "sell", sold, sold * 10))
            held -= sold
    a = replay(ops)["A"]

    bought = sum((op.amount for op in ops if op.kind == "buy"), D(0))
    assert a.cost + sum((d.cost for d in a.disposals), D(0)) == pytest.approx(bought)
    assert a.units == held


# --- The two-month rule ------------------------------------------------------------------------


def test_repurchase_windows() -> None:
    assert repurchase_window(dt.date(2026, 3, 31), listed=True) == (
        dt.date(2026, 1, 31),
        dt.date(2026, 5, 31),
    )
    assert repurchase_window(dt.date(2026, 12, 31), listed=True)[1] == dt.date(2027, 2, 28)
    assert repurchase_window(dt.date(2026, 3, 15), listed=False) == (
        dt.date(2025, 3, 15),
        dt.date(2027, 3, 15),
    )


def test_a_loss_with_a_repurchase_is_flagged() -> None:
    ops = [
        buy("b1", "2026-01-10", "10", "1000"),
        sell("s1", "2026-03-10", "10", "800"),  # loses 200
        buy("b2", "2026-04-20", "10", "790"),  # bought back within two months
    ]
    disposals = replay(ops)["A"].disposals
    buys = [op for op in ops if op.kind == "buy"]

    assert repurchased(disposals, buys, listed=True) == {"s1"}
    late = [*buys[:1], buy("b2", "2026-06-20", "10", "790")]
    assert repurchased(disposals, late, listed=True) == set()
    assert repurchased(disposals, late, listed=False) == {"s1"}  # funds: one year


def test_a_gain_is_never_flagged() -> None:
    ops = [buy("b1", "2026-01-10", "10", "1000"), sell("s1", "2026-03-10", "10", "1200")]
    disposals = replay(ops)["A"].disposals

    assert repurchased(disposals, [*ops[:1], buy("b2", "2026-03-20", "1", "1")], True) == set()

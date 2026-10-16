from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from finance.money import CENT, round_cents, to_decimal

finite_decimals = st.decimals(
    min_value=Decimal("-1e12"), max_value=Decimal("1e12"), allow_nan=False, allow_infinity=False
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(Decimal("12.34"), Decimal("12.34")), (5, Decimal(5)), ("-0.10", Decimal("-0.10"))],
)
def test_to_decimal_accepts_exact_types(value: Decimal | int | str, expected: Decimal) -> None:
    assert to_decimal(value) == expected


@pytest.mark.parametrize("value", [0.1, True, None, [1]])
def test_to_decimal_rejects_floats_and_other_types(value: object) -> None:
    with pytest.raises(TypeError):
        to_decimal(value)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", "12,50", "abc", ""])
def test_to_decimal_rejects_invalid_or_non_finite(value: str) -> None:
    with pytest.raises(ValueError, match="amount"):
        to_decimal(value)


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        ("0.005", "0.01"),
        ("-0.005", "-0.01"),
        ("2.675", "2.68"),
        ("1.004", "1.00"),
        ("1234.5", "1234.50"),
        ("0.015", "0.02"),
    ],
)
def test_round_cents_uses_half_up(amount: str, expected: str) -> None:
    assert round_cents(Decimal(amount)) == Decimal(expected)


@given(finite_decimals)
def test_round_cents_properties(amount: Decimal) -> None:
    rounded = round_cents(amount)

    assert rounded == rounded.quantize(CENT)  # at most two decimals
    assert abs(rounded - amount) <= Decimal("0.005")  # never moves more than half a cent
    assert round_cents(rounded) == rounded  # idempotent

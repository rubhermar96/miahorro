import datetime as dt
from decimal import Decimal

import pytest

from importers.values import (
    detect_date_order,
    detect_decimal_comma,
    parse_amount,
    parse_date,
    plain,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1.234,56", "1234.56"),
        ("-1.234,56", "-1234.56"),
        ("1234,5", "1234.5"),
        ("12", "12"),
        ("-12,50 €", "-12.50"),
        ("12,50-", "-12.50"),
        ("(12,50)", "-12.50"),
        ("+3,00", "3.00"),
        (chr(0x2212) + "3,00", "-3.00"),  # minus sign
        ("1 234,56 EUR", "1234.56"),
        ("1.000.000,00", "1000000.00"),
    ],
)
def test_spanish_amounts(text: str, expected: str) -> None:
    assert parse_amount(text) == Decimal(expected)


@pytest.mark.parametrize(
    ("text", "expected"), [("1,234.56", "1234.56"), ("-12.5", "-12.5"), ("1234", "1234")]
)
def test_amounts_with_decimal_dot(text: str, expected: str) -> None:
    assert parse_amount(text, decimal_comma=False) == Decimal(expected)


@pytest.mark.parametrize("text", ["doce", "12,345,6", "1.23,45", "12.5", "--3", "1,2,3"])
def test_rejects_what_is_not_a_spanish_amount(text: str) -> None:
    with pytest.raises(ValueError, match="no es un importe"):
        parse_amount(text)


def test_empty_cells_and_typed_cells() -> None:
    assert parse_amount(None) is None
    assert parse_amount("  ") is None
    assert parse_amount(Decimal("-7.5")) == Decimal("-7.5")
    with pytest.raises(ValueError, match="fecha"):
        parse_amount(dt.date(2026, 1, 1))


def test_detects_the_decimal_separator_of_a_column() -> None:
    assert detect_decimal_comma(["1.234,56", "-12,00", "7"])
    assert not detect_decimal_comma(["1,234.56", "-12.00", "7"])
    assert detect_decimal_comma(["1.234", "7", None])  # no clue: Spanish


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("15/10/2026", dt.date(2026, 10, 15)),
        ("5-1-26", dt.date(2026, 1, 5)),
        ("15.10.2026", dt.date(2026, 10, 15)),
        ("2026-10-15", dt.date(2026, 10, 15)),
        ("2026-10-15T10:23:00", dt.date(2026, 10, 15)),
        ("15/10/2026 10:23", dt.date(2026, 10, 15)),
        ("20261015", dt.date(2026, 10, 15)),
        ("15 oct 2026", dt.date(2026, 10, 15)),
        ("15-Oct-26", dt.date(2026, 10, 15)),
        ("01-ene-2026", dt.date(2026, 1, 1)),
    ],
)
def test_spanish_dates(text: str, expected: dt.date) -> None:
    assert parse_date(text) == expected


def test_dates_from_spreadsheets() -> None:
    assert parse_date(dt.datetime(2026, 10, 15, 9, 30)) == dt.date(2026, 10, 15)  # noqa: DTZ001
    assert parse_date(Decimal(46310)) == dt.date(2026, 10, 15)  # Excel serial number
    assert parse_date(None) is None


@pytest.mark.parametrize("text", ["31/02/2026", "mañana", "15/13/2026", "12,50"])
def test_rejects_what_is_not_a_date(text: str) -> None:
    with pytest.raises(ValueError, match="no es una fecha"):
        parse_date(text)


def test_detects_the_order_of_a_date_column() -> None:
    assert detect_date_order(["01/02/2026", "15/02/2026"]) == "dmy"
    assert detect_date_order(["2026-02-01"]) == "dmy"  # four-digit years are read anyway
    assert detect_date_order(["02/15/2026", "02/01/2026"]) == "mdy"


def test_plain_text_for_comparisons() -> None:
    assert plain("  Fecha Operación ") == "fecha operacion"

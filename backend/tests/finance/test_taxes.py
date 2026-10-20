from decimal import Decimal

import pytest

from finance.taxes import Bracket, band_rate, progressive_tax, scale_tax

SAVINGS = [
    Bracket(Decimal(6000), Decimal(19)),
    Bracket(Decimal(50000), Decimal(21)),
    Bracket(Decimal(200000), Decimal(23)),
    Bracket(Decimal(300000), Decimal(27)),
    Bracket(None, Decimal(30)),
]
CO2 = [
    Bracket(Decimal(120), Decimal(0)),
    Bracket(Decimal(159), Decimal("4.75")),
    Bracket(Decimal(199), Decimal("9.75")),
    Bracket(None, Decimal("14.75")),
]


@pytest.mark.parametrize(
    ("gain", "tax"),
    [
        ("0", "0"),
        ("-500", "0"),
        ("1000", "190"),
        ("6000", "1140"),
        ("10000", "1980"),  # 6.000 * 19 % + 4.000 * 21 %
        ("60000", "12680"),  # 1.140 + 44.000 * 21 % + 10.000 * 23 %
        ("400000", "101880"),  # … + 150.000 * 23 % + 100.000 * 27 % + 100.000 * 30 %
    ],
)
def test_savings_scale_goes_by_tranches(gain: str, tax: str) -> None:
    assert progressive_tax(Decimal(gain), SAVINGS) == Decimal(tax)


def test_balearic_itp_example_of_a_villa() -> None:
    # 400.000 * 8 % + 200.000 * 9 % + 400.000 * 10 % + 800.000 * 12 % (guiafiscal.es)
    balearic = [
        Bracket(Decimal(400000), Decimal(8)),
        Bracket(Decimal(600000), Decimal(9)),
        Bracket(Decimal(1000000), Decimal(10)),
        Bracket(Decimal(2000000), Decimal(12)),
        Bracket(None, Decimal(13)),
    ]
    assert progressive_tax(Decimal(1800000), balearic) == Decimal(186000)


@pytest.mark.parametrize(
    ("co2", "rate"),
    [(0, "0"), (120, "0"), (121, "4.75"), (159, "4.75"), (160, "9.75"), (199, "9.75"),
     (200, "14.75"), (350, "14.75")],
)  # fmt: skip
def test_registration_band_by_co2(co2: int, rate: str) -> None:
    assert band_rate(Decimal(co2), CO2) == Decimal(rate)


def test_scale_tax_by_band_applies_one_rate_to_everything() -> None:
    igic = [Bracket(Decimal(200000), Decimal(3)), Bracket(None, Decimal(7))]
    assert scale_tax(Decimal(150000), igic, marginal=False) == Decimal(4500)
    assert scale_tax(Decimal(250000), igic, marginal=False) == Decimal(17500)
    assert scale_tax(Decimal(250000), igic) == Decimal(9500)  # by tranches
    assert scale_tax(Decimal(1000), []) == 0

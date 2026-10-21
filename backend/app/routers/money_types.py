"""Exact amounts and rates in the API (RNF-04).

They travel as strings ("-12.50", "2.1500"). JSON numbers with decimals are refused: a client
that parsed them as floats might already have lost precision.
"""

from decimal import Decimal
from typing import Annotated, Any

from pydantic import BeforeValidator, PlainSerializer, WithJsonSchema

from finance.money import CENT, to_decimal

_MAX_AMOUNT = Decimal("1e12")
_RATE_STEP = Decimal("0.0001")


def _exact(value: Any, what: str) -> Decimal:
    if isinstance(value, float):
        raise ValueError(f'{what} se envía como texto, por ejemplo "12.50".')
    try:
        return to_decimal(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{what} no es válido.") from exc


def _parse_money(value: Any) -> Decimal:
    amount = _exact(value, "El importe")
    if amount != amount.quantize(CENT):
        raise ValueError("El importe tiene como mucho dos decimales.")
    if abs(amount) >= _MAX_AMOUNT:
        raise ValueError("El importe es demasiado grande.")
    return amount.quantize(CENT)


def _parse_rate(value: Any) -> Decimal:
    rate = _exact(value, "El tipo de interés")
    if rate != rate.quantize(_RATE_STEP):
        raise ValueError("El tipo de interés tiene como mucho cuatro decimales.")
    if not Decimal(0) <= rate <= Decimal(100):
        raise ValueError("El tipo de interés debe estar entre 0 y 100 %.")
    return rate.quantize(_RATE_STEP)


Money = Annotated[
    Decimal,
    BeforeValidator(_parse_money),
    PlainSerializer(lambda value: f"{value:.2f}", return_type=str, when_used="json"),
    WithJsonSchema({"type": "string", "pattern": r"^-?\d+(\.\d{1,2})?$", "examples": ["-12.50"]}),
]

Rate = Annotated[
    Decimal,
    BeforeValidator(_parse_rate),
    PlainSerializer(lambda value: f"{value:.4f}", return_type=str, when_used="json"),
    WithJsonSchema({"type": "string", "pattern": r"^\d+(\.\d{1,4})?$", "examples": ["2.15"]}),
]

_UNIT_STEP = Decimal("0.000001")
_MAX_UNITS = Decimal("1e13")


def _parse_units(value: Any) -> Decimal:
    units = _exact(value, "La cantidad")
    if units != units.quantize(_UNIT_STEP):
        raise ValueError("La cantidad tiene como mucho seis decimales.")
    if not Decimal(0) <= units < _MAX_UNITS:
        raise ValueError("La cantidad no es válida.")
    return units.quantize(_UNIT_STEP)


def _show_units(value: Decimal) -> str:
    """Six decimals at most, without trailing zeros: "12.5", "3"."""
    text = f"{value.quantize(_UNIT_STEP):f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


# Participaciones, shares and prices per unit: up to six decimals.
Units = Annotated[
    Decimal,
    BeforeValidator(_parse_units),
    PlainSerializer(_show_units, return_type=str, when_used="json"),
    WithJsonSchema({"type": "string", "pattern": r"^\d+(\.\d{1,6})?$", "examples": ["12.345678"]}),
]

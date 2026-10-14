"""Money primitives.

Rounding policy (RNF-04): amounts are rounded to the cent with ROUND_HALF_UP, the usual
commercial rounding in Spain. Halves round away from zero: 0.005 -> 0.01 and -0.005 -> -0.01.
Round only when a value is stored or shown, never in intermediate steps of a calculation.
"""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENT = Decimal("0.01")


def to_decimal(value: Decimal | int | str) -> Decimal:
    """Convert a value to Decimal, refusing floats and non-finite numbers.

    Floats are rejected even when they look harmless: 0.1 + 0.2 != 0.3.
    Strings must use a dot as decimal separator; parsing Spanish formats belongs to importers.
    """
    if isinstance(value, bool) or not isinstance(value, Decimal | int | str):
        raise TypeError(f"Amounts must be Decimal, int or str, not {type(value).__name__}")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"Not a valid amount: {value!r}") from exc
    if not result.is_finite():
        raise ValueError(f"Not a finite amount: {value!r}")
    return result


def round_cents(amount: Decimal) -> Decimal:
    """Round an amount to the cent using ROUND_HALF_UP."""
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)

"""Tax scales (RF-CAL-01, RF-CAL-04, RF-CAL-07): progressive tranches and flat rates chosen by
band. The rates themselves live in the reference tables, never in code."""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

_ZERO = Decimal(0)
_HUNDRED = Decimal(100)


@dataclass(frozen=True)
class Bracket:
    up_to: Decimal | None  # upper limit of the tranche; None for the last one
    rate: Decimal  # percent


def progressive_tax(base: Decimal, brackets: Sequence[Bracket]) -> Decimal:
    """Each rate applies only to the part of the base inside its tranche, like the savings
    scale of IRPF: 10.000 € pay 19 % on the first 6.000 € and 21 % on the other 4.000 €."""
    if base <= 0:
        return _ZERO
    tax = _ZERO
    lower = _ZERO
    for bracket in brackets:
        top = base if bracket.up_to is None else min(base, bracket.up_to)
        if top > lower:
            tax += (top - lower) * bracket.rate / _HUNDRED
        if bracket.up_to is None or base <= bracket.up_to:
            break
        lower = bracket.up_to
    return tax


def band_rate(base: Decimal, brackets: Sequence[Bracket]) -> Decimal:
    """The rate of the band the whole base falls in (the registration tax works like this:
    the CO₂ band sets one rate for the whole price)."""
    for bracket in brackets:
        if bracket.up_to is None or base <= bracket.up_to:
            return bracket.rate
    return brackets[-1].rate if brackets else _ZERO


def scale_tax(base: Decimal, brackets: Sequence[Bracket], *, marginal: bool = True) -> Decimal:
    """Tax on `base`: by tranches, or the band's rate on the whole base."""
    if base <= 0 or not brackets:
        return _ZERO
    if marginal:
        return progressive_tax(base, brackets)
    return base * band_rate(base, brackets) / _HUNDRED

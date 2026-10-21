"""Investment holdings by FIFO (RF-INV-02, RF-INV-05), the method Hacienda requires for
homogeneous securities (art. 37.2 LIRPF). Pure functions on exact decimals.

Rules applied:
- A purchase is a lot: its date and its cost, the purchase fee included.
- A sale takes the oldest lots first. What is received, net of the sale fee, is shared out in
  proportion to the units, and each part against its lot's cost is a gain or a loss.
- A transfer between funds (traspaso, art. 94 LIRPF) pays no tax: the oldest units leave the
  source and the units received keep their dates and costs.
- A split changes the units of every lot; dates and costs stay.
- Dividends, withholdings and standalone fees are kept apart from the lots.
"""

import datetime as dt
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

type OperationKind = Literal["buy", "sell", "dividend", "fee", "split", "transfer"]

_ZERO = Decimal(0)
# Units come from statements with up to six decimals; a difference below that is rounding.
EPSILON = Decimal("0.000001")


@dataclass(frozen=True)
class Operation:
    id: str
    investment: str
    date: dt.date
    kind: OperationKind
    units: Decimal = _ZERO  # bought, sold or transferred out
    amount: Decimal = _ZERO  # paid or received before fees; dividend gross; fee charged
    fee: Decimal = _ZERO  # commission of a purchase or a sale
    withholding: Decimal = _ZERO  # sale or dividend
    ratio: Decimal = _ZERO  # split: units after for each unit before
    target: str | None = None  # transfer: the fund that receives
    target_units: Decimal = _ZERO  # transfer: units received


@dataclass
class Lot:
    acquired: dt.date
    units: Decimal
    cost: Decimal
    origin: str  # the purchase it comes from, kept through transfers


@dataclass(frozen=True)
class Disposal:
    """The part of a sale that takes one lot."""

    sale: str
    investment: str
    date: dt.date
    acquired: dt.date
    units: Decimal
    cost: Decimal
    proceeds: Decimal
    origin: str

    @property
    def gain(self) -> Decimal:
        return self.proceeds - self.cost


@dataclass
class Holding:
    lots: list[Lot] = field(default_factory=list)
    disposals: list[Disposal] = field(default_factory=list)
    dividends: list[Operation] = field(default_factory=list)
    fees: list[Operation] = field(default_factory=list)
    sale_withholdings: list[Operation] = field(default_factory=list)

    @property
    def units(self) -> Decimal:
        return sum((lot.units for lot in self.lots), _ZERO)

    @property
    def cost(self) -> Decimal:
        return sum((lot.cost for lot in self.lots), _ZERO)


class PortfolioError(ValueError):
    """An operation that cannot happen: selling or moving units that are not there."""

    def __init__(self, operation: Operation, held: Decimal) -> None:
        super().__init__(f"Operation {operation.id} needs {operation.units} units, {held} held")
        self.operation = operation
        self.held = held


def _take(holding: Holding, units: Decimal, operation: Operation) -> list[Lot]:
    """Remove `units` from the oldest lots; the parts taken, each with its share of cost."""
    held = holding.units
    if units > held + EPSILON:
        raise PortfolioError(operation, held)
    remaining = min(units, held)
    taken: list[Lot] = []
    while remaining > 0 and holding.lots:
        lot = holding.lots[0]
        if lot.units <= remaining + EPSILON:
            taken.append(holding.lots.pop(0))
            remaining -= lot.units
        else:
            cost = lot.cost * remaining / lot.units
            taken.append(Lot(lot.acquired, remaining, cost, lot.origin))
            lot.units -= remaining
            lot.cost -= cost
            remaining = _ZERO
    return taken


def _shares(total: Decimal, parts: Sequence[Decimal]) -> list[Decimal]:
    """Split `total` in proportion to `parts`; the last one takes what is left so the shares
    add up exactly."""
    whole = sum(parts, _ZERO)
    if whole == 0:
        return [_ZERO for _ in parts]
    result = [total * part / whole for part in parts[:-1]]
    return [*result, total - sum(result, _ZERO)]


def replay(operations: Iterable[Operation]) -> dict[str, Holding]:
    """Every holding after the operations, applied by date and, within a day, in the order
    given (the order they were entered)."""
    holdings: dict[str, Holding] = {}

    def holding(investment: str) -> Holding:
        return holdings.setdefault(investment, Holding())

    for op in sorted(operations, key=lambda o: o.date):  # stable: keeps the order of a day
        own = holding(op.investment)
        if op.kind == "buy":
            own.lots.append(Lot(op.date, op.units, op.amount + op.fee, op.id))
        elif op.kind == "sell":
            taken = _take(own, op.units, op)
            proceeds = _shares(op.amount - op.fee, [lot.units for lot in taken])
            own.disposals.extend(
                Disposal(
                    sale=op.id,
                    investment=op.investment,
                    date=op.date,
                    acquired=lot.acquired,
                    units=lot.units,
                    cost=lot.cost,
                    proceeds=part,
                    origin=lot.origin,
                )
                for lot, part in zip(taken, proceeds, strict=True)
            )
            if op.withholding:
                own.sale_withholdings.append(op)
        elif op.kind == "transfer":
            if op.target is None:
                raise ValueError(f"Transfer {op.id} has no target")
            taken = _take(own, op.units, op)
            received = _shares(op.target_units, [lot.units for lot in taken])
            holding(op.target).lots.extend(
                Lot(lot.acquired, units, lot.cost, lot.origin)
                for lot, units in zip(taken, received, strict=True)
            )
            # Lots keep their dates: a later purchase may be older than what arrives.
            holding(op.target).lots.sort(key=lambda lot: lot.acquired)
        elif op.kind == "split":
            for lot in own.lots:
                lot.units *= op.ratio
        elif op.kind == "dividend":
            own.dividends.append(op)
        else:  # fee
            own.fees.append(op)
    return holdings


# --- The two-month rule ------------------------------------------------------------------------


def _add_months(date: dt.date, months: int) -> dt.date:
    total = date.month - 1 + months
    year, month = date.year + total // 12, total % 12 + 1
    for day in (date.day, 30, 29, 28):
        try:
            return dt.date(year, month, day)
        except ValueError:
            continue
    raise AssertionError("unreachable")


def repurchase_window(sale: dt.date, listed: bool) -> tuple[dt.date, dt.date]:
    """Art. 33.5 LIRPF: a loss does not count yet if homogeneous securities were bought in the
    two months before or after the sale (one year if they are not listed, like funds)."""
    months = 2 if listed else 12
    return _add_months(sale, -months), _add_months(sale, months)


def repurchased(disposals: Sequence[Disposal], buys: Iterable[Operation], listed: bool) -> set[str]:
    """Sales with a loss and a purchase of the same security inside the window (other than
    the purchases that sale itself used up)."""
    flagged: set[str] = set()
    by_sale: dict[str, list[Disposal]] = {}
    for part in disposals:
        by_sale.setdefault(part.sale, []).append(part)
    buys = list(buys)
    for sale, parts in by_sale.items():
        if sum((p.gain for p in parts), _ZERO) >= 0:
            continue
        start, end = repurchase_window(parts[0].date, listed)
        used = {p.origin for p in parts}
        if any(start <= buy.date <= end and buy.id not in used for buy in buys):
            flagged.add(sale)
    return flagged

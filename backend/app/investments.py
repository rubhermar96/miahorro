"""Investments (RF-INV-01, 02, 03, 05): the user's operations replayed by FIFO, what each
holding is worth today and the money each operation moves in an account."""

import datetime as dt
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clock
from app.defaults import ensure_default_categories
from app.models.investments import Investment, InvestmentOperation, InvestmentPrice
from app.models.transactions import Category, Transaction
from app.models.user import User
from app.ownership import owned
from finance.money import round_cents
from finance.portfolio import Disposal, Holding, Lot, Operation, PortfolioError, replay

_ZERO = Decimal(0)

# Funds move to funds and pension plans to pension plans without paying tax (art. 94 LIRPF;
# movilización of pension plans). ETFs and shares cannot be transferred that way.
TRANSFER_FAMILY = {"fund": "fund", "pension_plan": "pension_plan"}
# Listed securities: two months for the repurchase rule; the rest, one year.
LISTED = ("etf", "stock")

type PriceSource = Literal["manual", "operation"]


class InvestmentError(ValueError):
    """An operation that would leave the portfolio impossible, explained for the user."""


def units_text(value: Decimal) -> str:
    """Spanish style, up to six decimals: 1.234,5."""
    text = f"{value.quantize(Decimal('0.000001')):,f}".rstrip("0").rstrip(".")
    return text.replace(",", "_").replace(".", ",").replace("_", ".")


def to_operation(row: InvestmentOperation) -> Operation:
    ratio = (
        Decimal(row.split_to) / Decimal(row.split_from)
        if row.split_from and row.split_to
        else _ZERO
    )
    return Operation(
        id=str(row.id),
        investment=str(row.investment_id),
        date=row.date,
        kind=row.kind,  # type: ignore[arg-type]  # constrained in the database
        units=row.units,
        amount=row.amount,
        fee=row.fee,
        withholding=row.withholding,
        ratio=ratio,
        target=str(row.target_investment_id) if row.target_investment_id else None,
        target_units=row.target_units or _ZERO,
    )


def operations_of(db: Session, user: User) -> list[InvestmentOperation]:
    """All the user's operations, in the order they happened and were entered."""
    return list(
        db.scalars(
            owned(InvestmentOperation, user).order_by(
                InvestmentOperation.date, InvestmentOperation.created_at
            )
        )
    )


def holdings(
    db: Session, user: User, rows: Iterable[InvestmentOperation] | None = None
) -> dict[uuid.UUID, Holding]:
    """Every holding after the operations (the stored ones unless others are given)."""
    rows = list(rows) if rows is not None else operations_of(db, user)
    try:
        result = replay(to_operation(row) for row in rows)
    except PortfolioError as exc:
        raise InvestmentError(_explain(db, exc)) from exc
    return {uuid.UUID(key): value for key, value in result.items()}


def _explain(db: Session, error: PortfolioError) -> str:
    investment = db.get(Investment, uuid.UUID(error.operation.investment))
    name = investment.name if investment else "la inversión"
    return (
        f"El {error.operation.date:%d/%m/%Y} «{name}» tenía {units_text(error.held)} "
        f"participaciones: no se pueden sacar {units_text(error.operation.units)}. Revisa las "
        "fechas y las cantidades."
    )


# --- Prices -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Price:
    value: Decimal | None
    date: dt.date | None
    source: PriceSource | None


def latest_prices(db: Session, user: User, today: dt.date) -> dict[uuid.UUID, Price]:
    """The most recent price of each investment: typed in by hand, or the one of a purchase or
    sale (its amount over its units), whichever is newer; by hand wins on the same day."""
    best: dict[uuid.UUID, Price] = {}

    def offer(investment_id: uuid.UUID, price: Price) -> None:
        current = best.get(investment_id)
        if current is None or (price.date or dt.date.min) > (current.date or dt.date.min):
            best[investment_id] = price

    trades = db.scalars(
        owned(InvestmentOperation, user)
        .where(
            InvestmentOperation.kind.in_(("buy", "sell")),
            InvestmentOperation.units > 0,
            InvestmentOperation.date <= today,
        )
        .order_by(InvestmentOperation.date, InvestmentOperation.created_at)
    )
    for trade in trades:
        implied = (trade.amount / trade.units).quantize(Decimal("0.000001"), ROUND_HALF_UP)
        offer(trade.investment_id, Price(implied, trade.date, "operation"))
    manual = db.scalars(
        owned(InvestmentPrice, user)
        .where(InvestmentPrice.date <= today)
        .order_by(InvestmentPrice.date)
    )
    for row in manual:
        current = best.get(row.investment_id)
        if current is None or current.date is None or row.date >= current.date:
            best[row.investment_id] = Price(row.price, row.date, "manual")
    return best


# --- Summaries --------------------------------------------------------------------------------


@dataclass(frozen=True)
class Summary:
    units: Decimal
    cost: Decimal
    average_cost: Decimal | None
    price: Price
    value: Decimal | None
    gain: Decimal | None
    gain_percent: Decimal | None
    realized_total: Decimal
    realized_year: Decimal
    dividends_year: Decimal
    withholding_year: Decimal
    lots: list[Lot]


def summarize(holding: Holding | None, price: Price | None, today: dt.date) -> Summary:
    holding = holding or Holding()
    price = price or Price(None, None, None)
    units = holding.units
    cost = holding.cost
    value = round_cents(units * price.value) if price.value is not None else None
    if units == 0:
        value = Decimal("0.00")
    gain = value - round_cents(cost) if value is not None else None
    percent = (
        (gain * 100 / cost).quantize(Decimal("0.01"), ROUND_HALF_UP)
        if gain is not None and cost > 0
        else None
    )
    this_year = [d for d in holding.disposals if d.date.year == today.year]
    dividends = [d for d in holding.dividends if d.date.year == today.year]
    withheld = [*dividends, *(s for s in holding.sale_withholdings if s.date.year == today.year)]
    return Summary(
        units=units,
        cost=round_cents(cost),
        average_cost=(cost / units).quantize(Decimal("0.000001"), ROUND_HALF_UP) if units else None,
        price=price,
        value=value,
        gain=gain,
        gain_percent=percent,
        realized_total=round_cents(sum((d.gain for d in holding.disposals), _ZERO)),
        realized_year=round_cents(sum((d.gain for d in this_year), _ZERO)),
        dividends_year=round_cents(sum((d.amount for d in dividends), _ZERO)),
        withholding_year=round_cents(sum((w.withholding for w in withheld), _ZERO)),
        lots=list(holding.lots),
    )


def disposals_by_sale(holding: Holding) -> dict[str, list[Disposal]]:
    result: dict[str, list[Disposal]] = {}
    for part in holding.disposals:
        result.setdefault(part.sale, []).append(part)
    return result


# --- The money an operation moves ---------------------------------------------------------------


def _category(db: Session, user: User, name: str, kind: str) -> uuid.UUID | None:
    ensure_default_categories(db, user)
    db.flush()
    return db.scalar(
        owned(Category, user)
        .where(Category.name == name, Category.kind == kind, Category.archived_at.is_(None))
        .limit(1)
        .with_only_columns(Category.id)
    )


def cash_movement(
    db: Session, user: User, investment: Investment, row: InvestmentOperation, account_id: uuid.UUID
) -> Transaction | None:
    """The movement an operation makes in the account it is paid from or into. Buying and
    selling only change the form of the money (kind `investment`); a dividend is income and a
    standalone fee an expense."""
    pension = investment.kind == "pension_plan"
    kind = "investment"
    category: uuid.UUID | None = None
    if row.kind == "buy":
        amount = -(row.amount + row.fee)
        text = f"{'Aportación a' if pension else 'Compra de'} {investment.name}"
    elif row.kind == "sell":
        amount = row.amount - row.fee - row.withholding
        text = f"{'Rescate de' if pension else 'Venta de'} {investment.name}"
    elif row.kind == "dividend":
        amount = row.amount - row.withholding
        text, kind = f"Dividendo de {investment.name}", "income"
        category = _category(db, user, "Intereses y dividendos", "income")
    elif row.kind == "fee":
        amount = -row.amount
        text, kind = f"Comisión de {investment.name}", "expense"
        category = _category(db, user, "Comisiones bancarias", "expense")
    else:
        return None
    if amount == 0:
        return None
    movement = Transaction(
        user_id=user.id,
        account_id=account_id,
        date=row.date,
        amount=amount,
        kind=kind,
        description=text[:140],
        category_id=category,
        tags=[],
        source="manual",
        created_at=clock.now(),
        updated_at=clock.now(),
    )
    db.add(movement)
    db.flush()
    return movement


def drop_cash_movement(db: Session, row: InvestmentOperation) -> None:
    """Remove the movement an operation made, unless a bank statement has confirmed it."""
    if row.transaction_id is None:
        return
    movement = db.get(Transaction, row.transaction_id)
    row.transaction_id = None
    if movement is not None and movement.import_key is None:
        db.delete(movement)


def received_transfers(db: Session, investment: Investment) -> list[InvestmentOperation]:
    return list(
        db.scalars(
            select(InvestmentOperation).where(
                InvestmentOperation.target_investment_id == investment.id
            )
        )
    )

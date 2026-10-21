"""Investments: funds, ETFs, shares and pension plans, their operations and prices, FIFO
gains and the yearly report for the tax return (RF-INV-01, 02, 03, 05)."""

import datetime as dt
import uuid
from decimal import Decimal
from typing import Literal, Self

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select

from app import clock, investments
from app.auth.deps import CurrentUser, DbSession
from app.investments import InvestmentError, Price
from app.models.accounts import Account
from app.models.investments import Investment, InvestmentOperation, InvestmentPrice
from app.models.transactions import Transaction
from app.models.user import User
from app.ownership import get_owned_or_404, owned
from app.routers.money_types import Money, Units
from finance.isin import is_valid_isin, normalize_isin
from finance.money import round_cents
from finance.portfolio import Holding, repurchased

router = APIRouter(prefix="/api", tags=["investments"])

InvestmentKind = Literal["fund", "etf", "stock", "pension_plan"]
OperationKind = Literal["buy", "sell", "dividend", "fee", "split", "transfer"]


class InvestmentFields(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    kind: InvestmentKind = "fund"
    isin: str | None = Field(default=None, max_length=20)
    ticker: str | None = Field(default=None, max_length=16)
    account_id: uuid.UUID | None = Field(
        default=None, description="Where it is held; its money comes from and goes there"
    )
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def _tidy(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Ponle un nombre a la inversión.")
        return value

    @field_validator("isin")
    @classmethod
    def _isin(cls, value: str | None) -> str | None:
        if not value or not value.strip():
            return None
        code = normalize_isin(value)
        if not is_valid_isin(code):
            raise ValueError(
                "El ISIN no es válido: son 12 caracteres (dos letras de país, nueve letras o "
                "números y un dígito de control)."
            )
        return code

    @field_validator("ticker")
    @classmethod
    def _ticker(cls, value: str | None) -> str | None:
        return value.strip().upper() or None if value else None


class InvestmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    kind: InvestmentKind | None = None
    isin: str | None = Field(default=None, max_length=20)
    ticker: str | None = Field(default=None, max_length=16)
    account_id: uuid.UUID | None = None
    note: str | None = Field(default=None, max_length=2000)
    archived: bool | None = None


class LotOut(BaseModel):
    acquired: dt.date
    units: Units
    cost: Money


class InvestmentOut(InvestmentFields):
    id: uuid.UUID
    archived: bool
    units: Units
    cost: Money = Field(description="Cost of what is held, purchase fees included")
    average_cost: Units | None = Field(description="Cost per unit")
    price: Units | None = Field(description="Latest price per unit")
    price_date: dt.date | None
    price_source: Literal["manual", "operation"] | None = Field(
        description="manual: typed in · operation: that of the latest purchase or sale"
    )
    value: Money | None = Field(description="Null when there is no price yet")
    gain: Money | None = Field(description="Value minus cost (unrealized)")
    gain_percent: Decimal | None
    realized_total: Money = Field(description="FIFO gains and losses of every sale")
    realized_year: Money = Field(description="Those of this year")
    dividends_year: Money = Field(description="Gross dividends this year")
    withholding_year: Money = Field(description="Withheld this year on dividends and sales")


class InvestmentDetail(InvestmentOut):
    lots: list[LotOut] = Field(description="What is held, oldest first (FIFO order)")


def _out[T: InvestmentOut](
    model: type[T], row: Investment, holding: Holding | None, price: Price | None
) -> T:
    summary = investments.summarize(holding, price, clock.today())
    fields = {name: getattr(row, name) for name in InvestmentFields.model_fields}
    data = {
        **fields,
        "id": row.id,
        "archived": row.archived_at is not None,
        "units": summary.units,
        "cost": summary.cost,
        "average_cost": summary.average_cost,
        "price": summary.price.value,
        "price_date": summary.price.date,
        "price_source": summary.price.source,
        "value": summary.value,
        "gain": summary.gain,
        "gain_percent": summary.gain_percent,
        "realized_total": summary.realized_total,
        "realized_year": summary.realized_year,
        "dividends_year": summary.dividends_year,
        "withholding_year": summary.withholding_year,
    }
    if model is InvestmentDetail:
        data["lots"] = [
            LotOut(acquired=lot.acquired, units=lot.units, cost=round_cents(lot.cost))
            for lot in summary.lots
        ]
    return model.model_validate(data)


def _holdings(db: DbSession, user: User) -> dict[uuid.UUID, Holding]:
    try:
        return investments.holdings(db, user)
    except InvestmentError as exc:  # stored data never breaks the rules; just in case
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


def _check_account(db: DbSession, user: User, account_id: uuid.UUID | None) -> None:
    if account_id is not None:
        get_owned_or_404(db, Account, account_id, user)


def _check_isin_free(db: DbSession, user: User, isin: str | None, own: uuid.UUID | None) -> None:
    if isin is None:
        return
    other = db.scalar(
        owned(Investment, user).where(Investment.isin == isin, Investment.id != own).limit(1)
    )
    if other is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Ya tienes «{other.name}» con ese ISIN: Hacienda aplica FIFO a todas las "
            "participaciones de un mismo valor, así que van en la misma inversión aunque estén "
            "en distintos bancos.",
        )


@router.get("/investments")
def list_investments(
    user: CurrentUser, db: DbSession, include_archived: bool = False
) -> list[InvestmentOut]:
    """With what each one holds and is worth today; the most valuable first."""
    query = owned(Investment, user)
    if not include_archived:
        query = query.where(Investment.archived_at.is_(None))
    rows = list(db.scalars(query))
    held = _holdings(db, user)
    prices = investments.latest_prices(db, user, clock.today())
    result = [_out(InvestmentOut, row, held.get(row.id), prices.get(row.id)) for row in rows]
    return sorted(result, key=lambda i: (-(i.value or Decimal(0)), i.name.lower()))


@router.post("/investments", status_code=status.HTTP_201_CREATED)
def create_investment(body: InvestmentFields, user: CurrentUser, db: DbSession) -> InvestmentDetail:
    _check_account(db, user, body.account_id)
    _check_isin_free(db, user, body.isin, None)
    row = Investment(user_id=user.id, **body.model_dump())
    db.add(row)
    db.commit()
    return _out(InvestmentDetail, row, None, None)


@router.get("/investments/{investment_id}")
def read_investment(investment_id: uuid.UUID, user: CurrentUser, db: DbSession) -> InvestmentDetail:
    row = get_owned_or_404(db, Investment, investment_id, user)
    prices = investments.latest_prices(db, user, clock.today())
    return _out(InvestmentDetail, row, _holdings(db, user).get(row.id), prices.get(row.id))


@router.patch("/investments/{investment_id}")
def update_investment(
    investment_id: uuid.UUID, body: InvestmentUpdate, user: CurrentUser, db: DbSession
) -> InvestmentDetail:
    row = get_owned_or_404(db, Investment, investment_id, user)
    fields = body.model_fields_set
    merged = InvestmentFields.model_validate(
        {
            name: getattr(body, name) if name in fields else getattr(row, name)
            for name in InvestmentFields.model_fields
        }
    )
    if merged.kind != row.kind and db.scalar(
        select(InvestmentOperation.id)
        .where(
            (InvestmentOperation.investment_id == row.id)
            | (InvestmentOperation.target_investment_id == row.id),
            InvestmentOperation.kind == "transfer",
        )
        .limit(1)
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Tiene traspasos: no se puede cambiar de tipo sin borrarlos antes.",
        )
    _check_account(db, user, merged.account_id)
    _check_isin_free(db, user, merged.isin, row.id)
    for name, value in merged.model_dump().items():
        setattr(row, name, value)
    if body.archived is not None:
        row.archived_at = clock.now() if body.archived else None
    db.commit()
    return read_investment(row.id, user, db)


@router.delete("/investments/{investment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_investment(investment_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Response:
    """Its operations and prices go with it, and so do the movements they made in accounts
    that no bank statement has confirmed."""
    row = get_owned_or_404(db, Investment, investment_id, user)
    incoming = investments.received_transfers(db, row)
    if incoming:
        source = db.get(Investment, incoming[0].investment_id)
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Recibió un traspaso de «{source.name if source else 'otro fondo'}»: borra antes "
            "ese traspaso.",
        )
    rest = [op for op in investments.operations_of(db, user) if op.investment_id != row.id]
    _replayable(db, user, rest)
    for op in db.scalars(
        select(InvestmentOperation).where(InvestmentOperation.investment_id == row.id)
    ):
        investments.drop_cash_movement(db, op)
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Operations -------------------------------------------------------------------------------


class OperationIn(BaseModel):
    date: dt.date
    kind: OperationKind
    units: Units = Field(default=Decimal(0), description="Bought, sold or transferred out")
    amount: Money = Field(
        default=Decimal(0),
        description="Before fees: paid for a purchase, received for a sale; gross dividend; "
        "the fee itself; value of a transfer",
    )
    fee: Money = Field(default=Decimal(0), description="Commission of a purchase or sale")
    withholding: Money = Field(default=Decimal(0), description="Withheld on a sale or dividend")
    split_from: int | None = Field(default=None, ge=1, le=10000)
    split_to: int | None = Field(default=None, ge=1, le=10000)
    target_investment_id: uuid.UUID | None = None
    target_units: Units | None = None
    cash_account_id: uuid.UUID | None = Field(
        default=None, description="Account the money comes from or goes to; none: no movement"
    )
    note: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _complete(self) -> Self:
        if min(self.amount, self.fee, self.withholding) < 0:
            raise ValueError("Los importes no pueden ser negativos.")
        needs_units = self.kind in ("buy", "sell", "transfer")
        if needs_units and self.units <= 0:
            raise ValueError("Indica cuántas participaciones o acciones.")
        if self.kind in ("buy", "sell", "dividend", "fee") and self.amount <= 0:
            raise ValueError("Indica el importe.")
        if self.kind == "split" and (
            self.split_from is None or self.split_to is None or self.split_from == self.split_to
        ):
            raise ValueError("Indica cuántas acciones pasan a ser cuántas.")
        if self.kind == "transfer" and (self.target_investment_id is None or not self.target_units):
            raise ValueError("Indica el fondo de destino y las participaciones recibidas.")
        if self.withholding > self.amount:
            raise ValueError("La retención no puede ser mayor que el importe.")
        return self


class OperationOut(BaseModel):
    id: uuid.UUID
    investment_id: uuid.UUID
    date: dt.date
    kind: OperationKind
    direction: Literal["out", "in"] = Field(description="in: a transfer this investment received")
    units: Units
    amount: Money
    fee: Money
    withholding: Money
    split_from: int | None
    split_to: int | None
    target_investment_id: uuid.UUID | None
    target_units: Units | None
    price: Units | None = Field(description="Amount over units, for purchases and sales")
    cash_account_id: uuid.UUID | None
    transaction_id: uuid.UUID | None
    gain: Money | None = Field(description="Sales: FIFO gain or loss")
    note: str | None


def _operation_out(
    db: DbSession, row: InvestmentOperation, viewer: uuid.UUID, gains: dict[str, Decimal]
) -> OperationOut:
    movement = db.get(Transaction, row.transaction_id) if row.transaction_id else None
    priced = row.kind in ("buy", "sell") and row.units > 0
    return OperationOut(
        id=row.id,
        investment_id=row.investment_id,
        date=row.date,
        kind=row.kind,
        direction="in" if row.target_investment_id == viewer else "out",
        units=row.units,
        amount=row.amount,
        fee=row.fee,
        withholding=row.withholding,
        split_from=row.split_from,
        split_to=row.split_to,
        target_investment_id=row.target_investment_id,
        target_units=row.target_units,
        price=(row.amount / row.units).quantize(Decimal("0.000001")) if priced else None,
        cash_account_id=movement.account_id if movement else None,
        transaction_id=row.transaction_id,
        gain=round_cents(gains[str(row.id)]) if str(row.id) in gains else None,
        note=row.note,
    )


def _replayable(
    db: DbSession, user: User, rows: list[InvestmentOperation]
) -> dict[uuid.UUID, Holding]:
    try:
        return investments.holdings(db, user, sorted(rows, key=lambda r: (r.date, r.created_at)))
    except InvestmentError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


def _check_operation(
    db: DbSession, user: User, investment: Investment, body: OperationIn
) -> Investment | None:
    if body.kind == "transfer" and body.target_investment_id is not None:
        target = get_owned_or_404(db, Investment, body.target_investment_id, user)
        family = investments.TRANSFER_FAMILY.get(investment.kind)
        if family is None or investments.TRANSFER_FAMILY.get(target.kind) != family:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "Solo se traspasa de un fondo a otro fondo, o de un plan de pensiones a otro plan.",
            )
        if target.id == investment.id:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "El destino no puede ser el mismo fondo."
            )
        return target
    if body.cash_account_id is not None:
        get_owned_or_404(db, Account, body.cash_account_id, user)
    return None


def _fill(row: InvestmentOperation, body: OperationIn) -> None:
    transfer, split = body.kind == "transfer", body.kind == "split"
    row.date, row.kind = body.date, body.kind
    row.units = Decimal(0) if body.kind in ("dividend", "fee", "split") else body.units
    row.amount = Decimal(0) if split else body.amount
    row.fee = body.fee if body.kind in ("buy", "sell") else Decimal(0)
    row.withholding = body.withholding if body.kind in ("sell", "dividend") else Decimal(0)
    row.split_from = body.split_from if split else None
    row.split_to = body.split_to if split else None
    row.target_investment_id = body.target_investment_id if transfer else None
    row.target_units = body.target_units if transfer else None
    row.note = (body.note or "").strip() or None


def _sale_gains(held: dict[uuid.UUID, Holding], investment_id: uuid.UUID) -> dict[str, Decimal]:
    holding = held.get(investment_id)
    if holding is None:
        return {}
    return {
        sale: sum((p.gain for p in parts), Decimal(0))
        for sale, parts in investments.disposals_by_sale(holding).items()
    }


@router.get("/investments/{investment_id}/operations")
def list_operations(
    investment_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> list[OperationOut]:
    """Its operations and the transfers it received, newest first."""
    row = get_owned_or_404(db, Investment, investment_id, user)
    ops = db.scalars(
        owned(InvestmentOperation, user)
        .where(
            (InvestmentOperation.investment_id == row.id)
            | (InvestmentOperation.target_investment_id == row.id)
        )
        .order_by(InvestmentOperation.date.desc(), InvestmentOperation.created_at.desc())
    )
    gains = _sale_gains(_holdings(db, user), row.id)
    return [_operation_out(db, op, row.id, gains) for op in ops]


@router.post("/investments/{investment_id}/operations", status_code=status.HTTP_201_CREATED)
def add_operation(
    investment_id: uuid.UUID, body: OperationIn, user: CurrentUser, db: DbSession
) -> OperationOut:
    investment = get_owned_or_404(db, Investment, investment_id, user)
    _check_operation(db, user, investment, body)
    row = InvestmentOperation(
        id=uuid.uuid4(), user_id=user.id, investment_id=investment.id, created_at=clock.now()
    )
    _fill(row, body)
    held = _replayable(db, user, [*investments.operations_of(db, user), row])
    db.add(row)
    db.flush()
    if body.cash_account_id is not None:
        movement = investments.cash_movement(db, user, investment, row, body.cash_account_id)
        row.transaction_id = movement.id if movement else None
    db.commit()
    return _operation_out(db, row, investment.id, _sale_gains(held, investment.id))


@router.put("/investments/{investment_id}/operations/{operation_id}")
def replace_operation(
    investment_id: uuid.UUID,
    operation_id: uuid.UUID,
    body: OperationIn,
    user: CurrentUser,
    db: DbSession,
) -> OperationOut:
    investment = get_owned_or_404(db, Investment, investment_id, user)
    row = get_owned_or_404(db, InvestmentOperation, operation_id, user)
    if row.investment_id != investment.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    _check_operation(db, user, investment, body)
    with db.no_autoflush:
        _fill(row, body)
        held = _replayable(db, user, investments.operations_of(db, user))
    movement = db.get(Transaction, row.transaction_id) if row.transaction_id else None
    if movement is None or movement.import_key is None:
        investments.drop_cash_movement(db, row)
        db.flush()
        if body.cash_account_id is not None:
            new = investments.cash_movement(db, user, investment, row, body.cash_account_id)
            row.transaction_id = new.id if new else None
    db.commit()
    return _operation_out(db, row, investment.id, _sale_gains(held, investment.id))


@router.delete(
    "/investments/{investment_id}/operations/{operation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_operation(
    investment_id: uuid.UUID, operation_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> Response:
    row = get_owned_or_404(db, InvestmentOperation, operation_id, user)
    if investment_id not in (row.investment_id, row.target_investment_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    _replayable(db, user, [op for op in investments.operations_of(db, user) if op.id != row.id])
    investments.drop_cash_movement(db, row)
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Prices -----------------------------------------------------------------------------------


class PriceIn(BaseModel):
    date: dt.date
    price: Units

    @model_validator(mode="after")
    def _positive(self) -> Self:
        if self.price <= 0:
            raise ValueError("El precio debe ser mayor que cero.")
        return self


class PriceOut(PriceIn):
    id: uuid.UUID


@router.get("/investments/{investment_id}/prices")
def list_prices(investment_id: uuid.UUID, user: CurrentUser, db: DbSession) -> list[PriceOut]:
    get_owned_or_404(db, Investment, investment_id, user)
    rows = db.scalars(
        owned(InvestmentPrice, user)
        .where(InvestmentPrice.investment_id == investment_id)
        .order_by(InvestmentPrice.date.desc())
    )
    return [PriceOut(id=r.id, date=r.date, price=r.price) for r in rows]


@router.put("/investments/{investment_id}/prices")
def set_price(
    investment_id: uuid.UUID, body: PriceIn, user: CurrentUser, db: DbSession
) -> PriceOut:
    """The price (valor liquidativo) of a day; typing it again for that day replaces it."""
    get_owned_or_404(db, Investment, investment_id, user)
    if body.date > clock.today():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "El precio no puede ser de una fecha futura."
        )
    row = db.scalar(
        owned(InvestmentPrice, user).where(
            InvestmentPrice.investment_id == investment_id, InvestmentPrice.date == body.date
        )
    )
    if row is None:
        row = InvestmentPrice(user_id=user.id, investment_id=investment_id, date=body.date)
        db.add(row)
    row.price = body.price
    db.commit()
    return PriceOut(id=row.id, date=row.date, price=row.price)


@router.delete(
    "/investments/{investment_id}/prices/{price_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_price(
    investment_id: uuid.UUID, price_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> Response:
    row = get_owned_or_404(db, InvestmentPrice, price_id, user)
    if row.investment_id != investment_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Portfolio --------------------------------------------------------------------------------


class KindTotal(BaseModel):
    kind: InvestmentKind
    value: Money


class PortfolioOut(BaseModel):
    value: Money = Field(description="What everything with a price is worth today")
    cost: Money
    gain: Money = Field(description="Unrealized, of what has a price")
    gain_percent: Decimal | None
    unpriced: int = Field(description="Investments with units but no price yet")
    realized_year: Money
    dividends_year: Money
    withholding_year: Money
    year: int
    by_kind: list[KindTotal]


@router.get("/portfolio")
def portfolio(user: CurrentUser, db: DbSession) -> PortfolioOut:
    """The whole portfolio today: what it is worth, what it cost and this year's results."""
    rows = list_investments(user, db, include_archived=True)
    priced = [r for r in rows if r.value is not None]
    value = sum((r.value or Decimal(0) for r in priced), Decimal(0))
    cost = sum((r.cost for r in priced), Decimal(0))
    by_kind: dict[str, Decimal] = {}
    for r in priced:
        if r.value:
            by_kind[r.kind] = by_kind.get(r.kind, Decimal(0)) + r.value
    return PortfolioOut(
        value=value,
        cost=cost,
        gain=value - cost,
        gain_percent=((value - cost) * 100 / cost).quantize(Decimal("0.01")) if cost else None,
        unpriced=sum(1 for r in rows if r.value is None and r.units > 0),
        realized_year=sum((r.realized_year for r in rows if r.kind != "pension_plan"), Decimal(0)),
        dividends_year=sum((r.dividends_year for r in rows), Decimal(0)),
        withholding_year=sum((r.withholding_year for r in rows), Decimal(0)),
        year=clock.today().year,
        by_kind=[
            KindTotal(kind=kind, value=total)
            for kind, total in sorted(by_kind.items(), key=lambda item: -item[1])
        ],
    )


class SalePart(BaseModel):
    acquired: dt.date
    units: Units
    cost: Money
    proceeds: Money
    gain: Money


class SaleOut(BaseModel):
    operation_id: uuid.UUID
    investment_id: uuid.UUID
    name: str
    kind: InvestmentKind
    date: dt.date
    units: Units
    proceeds: Money = Field(description="Received, net of the sale fee")
    cost: Money = Field(description="Acquisition cost of the units sold, by FIFO")
    gain: Money
    withholding: Money
    taxable: bool = Field(description="False for pension plans: taxed as work income")
    repurchase_warning: bool = Field(
        description="A loss with a purchase of the same security close by (art. 33.5 LIRPF)"
    )
    parts: list[SalePart]


class DividendOut(BaseModel):
    operation_id: uuid.UUID
    investment_id: uuid.UUID
    name: str
    date: dt.date
    amount: Money
    withholding: Money


class TaxReportOut(BaseModel):
    year: int
    sales: list[SaleOut]
    gains: Money = Field(description="Taxable sales with a gain, added up")
    losses: Money = Field(description="Taxable sales with a loss, added up (negative)")
    net: Money
    sale_withholding: Money
    dividends: list[DividendOut]
    dividends_gross: Money
    dividends_withholding: Money
    pension_rescues: Money = Field(description="Received from pension plans (work income)")


@router.get("/portfolio/tax-report")
def tax_report(
    user: CurrentUser,
    db: DbSession,
    year: int | None = Query(default=None, ge=2000, le=2100),
) -> TaxReportOut:
    """Sales by FIFO and dividends of a year, as they go in the tax return (base del ahorro),
    to check against the broker's tax report."""
    year = year or clock.today().year
    held = _holdings(db, user)
    by_id = {row.id: row for row in db.scalars(owned(Investment, user))}
    ops = investments.operations_of(db, user)
    op_by_id = {str(op.id): op for op in ops}
    sales: list[SaleOut] = []
    dividends: list[DividendOut] = []
    for investment_id, holding in held.items():
        investment = by_id[investment_id]
        buys = [
            investments.to_operation(op)
            for op in ops
            if op.investment_id == investment_id and op.kind == "buy"
        ]
        flagged = (
            repurchased(holding.disposals, buys, listed=investment.kind in investments.LISTED)
            if investment.kind != "pension_plan"
            else set()
        )
        for sale, parts in investments.disposals_by_sale(holding).items():
            if parts[0].date.year != year:
                continue
            op = op_by_id[sale]
            sales.append(
                SaleOut(
                    operation_id=op.id,
                    investment_id=investment_id,
                    name=investment.name,
                    kind=investment.kind,
                    date=op.date,
                    units=op.units,
                    proceeds=round_cents(sum((p.proceeds for p in parts), Decimal(0))),
                    cost=round_cents(sum((p.cost for p in parts), Decimal(0))),
                    gain=round_cents(sum((p.gain for p in parts), Decimal(0))),
                    withholding=op.withholding,
                    taxable=investment.kind != "pension_plan",
                    repurchase_warning=sale in flagged,
                    parts=[
                        SalePart(
                            acquired=p.acquired,
                            units=p.units,
                            cost=round_cents(p.cost),
                            proceeds=round_cents(p.proceeds),
                            gain=round_cents(p.gain),
                        )
                        for p in parts
                    ],
                )
            )
        dividends += [
            DividendOut(
                operation_id=uuid.UUID(d.id),
                investment_id=investment_id,
                name=investment.name,
                date=d.date,
                amount=d.amount,
                withholding=d.withholding,
            )
            for d in holding.dividends
            if d.date.year == year
        ]
    sales.sort(key=lambda s: (s.date, s.name))
    dividends.sort(key=lambda d: (d.date, d.name))
    taxable = [s for s in sales if s.taxable]
    gains = sum((s.gain for s in taxable if s.gain > 0), Decimal(0))
    losses = sum((s.gain for s in taxable if s.gain < 0), Decimal(0))
    return TaxReportOut(
        year=year,
        sales=sales,
        gains=gains,
        losses=losses,
        net=gains + losses,
        sale_withholding=sum((s.withholding for s in taxable), Decimal(0)),
        dividends=dividends,
        dividends_gross=sum((d.amount for d in dividends), Decimal(0)),
        dividends_withholding=sum((d.withholding for d in dividends), Decimal(0)),
        pension_rescues=sum((s.proceeds for s in sales if not s.taxable), Decimal(0)),
    )

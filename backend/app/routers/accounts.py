"""Accounts, their remuneration and balance reconciliation (RF-CTA-01…04, 07, 08)."""

import datetime as dt
import uuid
from decimal import Decimal
from typing import Literal, Self, get_args

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import exists, select

from app import clock, goals, ledger
from app.auth.deps import CurrentUser, DbSession
from app.models.accounts import Account, AccountRate
from app.models.transactions import Transaction
from app.ownership import get_owned_or_404, owned
from app.routers.money_types import Money, Rate
from app.routers.schemas import Currency
from app.routers.transactions import TransactionOut

router = APIRouter(prefix="/api/accounts", tags=["accounts"])

AccountKind = Literal[
    "checking", "savings", "deposit", "credit_card", "cash", "wallet", "brokerage", "crypto"
]
Liquidation = Literal["daily", "monthly", "quarterly", "semiannual", "annual", "at_maturity"]

# Order in which kinds are listed: everyday money first.
_KIND_ORDER = {kind: index for index, kind in enumerate(get_args(AccountKind))}


class RateTier(BaseModel):
    up_to: Money | None = Field(default=None, description="Upper limit; null for the last tier")
    rate: Rate


class AccountRateIn(BaseModel):
    valid_from: dt.date
    tiers: list[RateTier] = Field(min_length=1, max_length=5)
    tae: Rate | None = None
    liquidation: Liquidation = "monthly"
    withholding: Rate = Decimal("19")

    @model_validator(mode="after")
    def _tiers_ascend(self) -> Self:
        *bounded, last = self.tiers
        if last.up_to is not None:
            raise ValueError("El último tramo no tiene límite: deja su importe vacío.")
        limits = [tier.up_to for tier in bounded if tier.up_to is not None]
        if len(limits) != len(bounded) or any(limit <= 0 for limit in limits):
            raise ValueError("Cada tramo, salvo el último, necesita un límite mayor que cero.")
        if limits != sorted(limits) or len(set(limits)) != len(limits):
            raise ValueError("Los límites de los tramos deben ir de menor a mayor.")
        return self


class AccountRateOut(AccountRateIn):
    id: uuid.UUID

    @classmethod
    def from_model(cls, rate: AccountRate) -> AccountRateOut:
        return cls.model_validate(
            {
                "id": rate.id,
                "valid_from": rate.valid_from,
                "tiers": rate.tiers,
                "tae": rate.tae,
                "liquidation": rate.liquidation,
                "withholding": rate.withholding,
            }
        )


class AccountFields(BaseModel):
    institution: str | None = Field(default=None, max_length=60)
    iban_last4: str | None = Field(default=None, pattern=r"^\d{4}$")
    is_joint: bool = False
    maturity_date: dt.date | None = None
    auto_renew: bool = False
    early_cancellation_note: str | None = Field(default=None, max_length=200)


class AccountIn(AccountFields):
    name: str = Field(min_length=1, max_length=60)
    kind: AccountKind
    currency: Currency = "EUR"
    opening_balance: Money = Decimal("0.00")
    opening_date: dt.date

    @model_validator(mode="after")
    def _maturity_after_opening(self) -> Self:
        if self.maturity_date is not None and self.maturity_date <= self.opening_date:
            raise ValueError("El vencimiento debe ser posterior a la fecha de apertura.")
        return self


class AccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    kind: AccountKind | None = None
    institution: str | None = Field(default=None, max_length=60)
    iban_last4: str | None = Field(default=None, pattern=r"^\d{4}$")
    is_joint: bool | None = None
    opening_balance: Money | None = None
    opening_date: dt.date | None = None
    maturity_date: dt.date | None = None
    auto_renew: bool | None = None
    early_cancellation_note: str | None = Field(default=None, max_length=200)
    archived: bool | None = None


class AccountOut(AccountIn):
    id: uuid.UUID
    balance: Money
    reserved: Money = Field(description="Set aside for savings goals")
    available: Money = Field(description="Balance minus what goals hold")
    archived: bool
    current_rate: AccountRateOut | None


class ReconcileIn(BaseModel):
    balance: Money = Field(description="The real balance the bank shows")
    date: dt.date | None = None


class ReconcileOut(BaseModel):
    adjustment: TransactionOut | None
    balance: Money


def _out(account: Account, balance: Decimal, reserved: Decimal = Decimal(0)) -> AccountOut:
    rate = ledger.rate_on(account, clock.today())
    return AccountOut.model_validate(
        {
            "id": account.id,
            "name": account.name,
            "kind": account.kind,
            "institution": account.institution,
            "iban_last4": account.iban_last4,
            "currency": account.currency,
            "opening_balance": account.opening_balance,
            "opening_date": account.opening_date,
            "is_joint": account.is_joint,
            "maturity_date": account.maturity_date,
            "auto_renew": account.auto_renew,
            "early_cancellation_note": account.early_cancellation_note,
            "balance": balance,
            "reserved": reserved,
            "available": balance - reserved,
            "archived": account.archived_at is not None,
            "current_rate": AccountRateOut.from_model(rate) if rate else None,
        }
    )


def _clean(text: str | None) -> str | None:
    return (text or "").strip() or None


@router.get("")
def list_accounts(
    user: CurrentUser, db: DbSession, include_archived: bool = False
) -> list[AccountOut]:
    query = owned(Account, user)
    if not include_archived:
        query = query.where(Account.archived_at.is_(None))
    accounts = sorted(db.scalars(query), key=lambda a: (_KIND_ORDER[a.kind], a.name.lower()))
    totals = ledger.transaction_totals(db, user)
    reserved = goals.reserved_by_account(db, user)
    return [
        _out(
            account,
            account.opening_balance + totals.get(account.id, Decimal(0)),
            reserved.get(account.id, Decimal(0)),
        )
        for account in accounts
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_account(body: AccountIn, user: CurrentUser, db: DbSession) -> AccountOut:
    account = Account(
        user_id=user.id,
        name=body.name.strip(),
        kind=body.kind,
        institution=_clean(body.institution),
        iban_last4=body.iban_last4,
        currency=body.currency,
        opening_balance=body.opening_balance,
        opening_date=body.opening_date,
        is_joint=body.is_joint,
        maturity_date=body.maturity_date,
        auto_renew=body.auto_renew,
        early_cancellation_note=_clean(body.early_cancellation_note),
    )
    db.add(account)
    db.commit()
    return _out(account, account.opening_balance)


@router.get("/{account_id}")
def read_account(account_id: uuid.UUID, user: CurrentUser, db: DbSession) -> AccountOut:
    account = get_owned_or_404(db, Account, account_id, user)
    return _out(account, ledger.balance_of(db, account), goals.reserved_in(db, user, account))


@router.patch("/{account_id}")
def update_account(
    account_id: uuid.UUID, body: AccountUpdate, user: CurrentUser, db: DbSession
) -> AccountOut:
    account = get_owned_or_404(db, Account, account_id, user)
    changes = body.model_dump(exclude_unset=True)
    if "archived" in changes:
        archived = changes.pop("archived")
        account.archived_at = (account.archived_at or clock.now()) if archived else None
    for field in ("institution", "early_cancellation_note"):
        if field in changes:
            changes[field] = _clean(changes[field])
    if "name" in changes:
        changes["name"] = changes["name"].strip()
    for field, value in changes.items():
        if value is None and field in {"name", "kind", "opening_balance", "opening_date"}:
            continue  # required fields cannot be emptied
        setattr(account, field, value)
    if account.maturity_date is not None and account.maturity_date <= account.opening_date:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "El vencimiento debe ser posterior a la fecha de apertura.",
        )
    db.commit()
    return _out(account, ledger.balance_of(db, account), goals.reserved_in(db, user, account))


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(account_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Response:
    account = get_owned_or_404(db, Account, account_id, user)
    if db.scalar(select(exists().where(Transaction.account_id == account.id))):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "La cuenta tiene movimientos. Archívala para ocultarla sin perder el historial.",
        )
    db.delete(account)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Remuneration history ---------------------------------------------------------------------


@router.get("/{account_id}/rates")
def list_rates(account_id: uuid.UUID, user: CurrentUser, db: DbSession) -> list[AccountRateOut]:
    account = get_owned_or_404(db, Account, account_id, user)
    return [AccountRateOut.from_model(rate) for rate in account.rates]


@router.post("/{account_id}/rates", status_code=status.HTTP_201_CREATED)
def add_rate(
    account_id: uuid.UUID, body: AccountRateIn, user: CurrentUser, db: DbSession
) -> AccountRateOut:
    account = get_owned_or_404(db, Account, account_id, user)
    if any(rate.valid_from == body.valid_from for rate in account.rates):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Ya hay unas condiciones que empiezan ese mismo día."
        )
    rate = AccountRate(
        account_id=account.id,
        valid_from=body.valid_from,
        tiers=[tier.model_dump(mode="json") for tier in body.tiers],
        tae=body.tae,
        liquidation=body.liquidation,
        withholding=body.withholding,
    )
    db.add(rate)
    db.commit()
    return AccountRateOut.from_model(rate)


@router.delete("/{account_id}/rates/{rate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rate(
    account_id: uuid.UUID, rate_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> Response:
    account = get_owned_or_404(db, Account, account_id, user)
    rate = next((rate for rate in account.rates if rate.id == rate_id), None)
    if rate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    db.delete(rate)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Reconciliation ---------------------------------------------------------------------------


@router.post("/{account_id}/reconcile")
def reconcile(
    account_id: uuid.UUID, body: ReconcileIn, user: CurrentUser, db: DbSession
) -> ReconcileOut:
    """Match the bank: if the real balance differs, record the difference as an adjustment."""
    account = get_owned_or_404(db, Account, account_id, user)
    difference = body.balance - ledger.balance_of(db, account)
    if difference == 0:
        return ReconcileOut(adjustment=None, balance=body.balance)
    adjustment = Transaction(
        user_id=user.id,
        account_id=account.id,
        date=body.date or clock.today(),
        amount=difference,
        description="Ajuste de saldo",
        kind="adjustment",
        tags=[],
    )
    db.add(adjustment)
    db.commit()
    return ReconcileOut(adjustment=TransactionOut.from_model(adjustment), balance=body.balance)

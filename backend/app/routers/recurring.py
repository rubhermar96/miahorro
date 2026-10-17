"""Recurring income and expenses (RF-MOV-06) and the review tray."""

import datetime as dt
import uuid
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Query, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from app import clock
from app.auth.deps import CurrentUser, DbSession
from app.models.accounts import Account
from app.models.capture import RecurringItem
from app.models.transactions import Category, Transaction
from app.models.user import User
from app.ownership import get_owned_or_404, owned
from app.recurring import occurrences
from app.routers.money_types import Money
from app.routers.transactions import TransactionOut

router = APIRouter(prefix="/api", tags=["recurring"])

Frequency = Literal["weekly", "monthly", "quarterly", "semiannual", "yearly"]
# A captured payment the bank has not confirmed after this long goes to the review tray.
UNCONFIRMED_AFTER = dt.timedelta(days=7)
# An expected movement this late is reported as not arrived.
OVERDUE_AFTER = dt.timedelta(days=3)


class RecurringIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    account_id: uuid.UUID
    kind: Literal["expense", "income"]
    amount: Money = Field(description="Expected amount, positive")
    tolerance: Money = Field(
        default=Decimal(10), description="Percent the real amount may differ (bills vary)"
    )
    category_id: uuid.UUID | None = None
    match_text: str = Field(
        min_length=2, max_length=60, description="Text in the concept of the real movement"
    )
    frequency: Frequency = "monthly"
    next_date: dt.date

    @field_validator("name", "match_text")
    @classmethod
    def _tidy(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("amount")
    @classmethod
    def _positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("El importe esperado debe ser mayor que cero.")
        return value

    @field_validator("tolerance")
    @classmethod
    def _tolerance(cls, value: Decimal) -> Decimal:
        if not 0 <= value <= 50:
            raise ValueError("El margen va de 0 % a 50 %.")
        return value


class RecurringOut(RecurringIn):
    id: uuid.UUID
    last_transaction_id: uuid.UUID | None

    @classmethod
    def from_model(cls, item: RecurringItem) -> RecurringOut:
        return cls(
            id=item.id,
            name=item.name,
            account_id=item.account_id,
            kind=item.kind,
            amount=item.amount,
            tolerance=item.tolerance,
            category_id=item.category_id,
            match_text=item.match_text,
            frequency=item.frequency,
            next_date=item.next_date,
            last_transaction_id=item.last_transaction_id,
        )


class Upcoming(BaseModel):
    item_id: uuid.UUID
    name: str
    account_id: uuid.UUID
    date: dt.date
    amount: Money = Field(description="Signed: negative is money going out")
    overdue: bool = Field(description="Expected some days ago and not arrived")


class Inbox(BaseModel):
    unconfirmed: list[TransactionOut] = Field(
        description="Captured payments no statement has confirmed after a week"
    )
    overdue: list[Upcoming] = Field(description="Recurring movements that have not arrived")


def _check(db: DbSession, user: User, body: RecurringIn) -> None:
    get_owned_or_404(db, Account, body.account_id, user)
    if body.category_id is not None:
        get_owned_or_404(db, Category, body.category_id, user)


def _apply(item: RecurringItem, body: RecurringIn) -> None:
    item.name = body.name
    item.account_id = body.account_id
    item.kind = body.kind
    item.amount = body.amount
    item.tolerance = body.tolerance
    item.category_id = body.category_id
    item.match_text = body.match_text
    item.frequency = body.frequency
    item.next_date = body.next_date


@router.get("/recurring")
def list_recurring(user: CurrentUser, db: DbSession) -> list[RecurringOut]:
    items = db.scalars(owned(RecurringItem, user).order_by(RecurringItem.next_date))
    return [RecurringOut.from_model(item) for item in items]


@router.post("/recurring", status_code=status.HTTP_201_CREATED)
def create_recurring(body: RecurringIn, user: CurrentUser, db: DbSession) -> RecurringOut:
    _check(db, user, body)
    item = RecurringItem(user_id=user.id)
    _apply(item, body)
    db.add(item)
    db.commit()
    return RecurringOut.from_model(item)


@router.put("/recurring/{item_id}")
def update_recurring(
    item_id: uuid.UUID, body: RecurringIn, user: CurrentUser, db: DbSession
) -> RecurringOut:
    item = get_owned_or_404(db, RecurringItem, item_id, user)
    _check(db, user, body)
    _apply(item, body)
    db.commit()
    return RecurringOut.from_model(item)


@router.delete("/recurring/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recurring(item_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Response:
    db.delete(get_owned_or_404(db, RecurringItem, item_id, user))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _upcoming(db: DbSession, user: User, days: int) -> list[Upcoming]:
    today = clock.today()
    until = today + dt.timedelta(days=days)
    result: list[Upcoming] = []
    for item in db.scalars(owned(RecurringItem, user)):
        sign = -1 if item.kind == "expense" else 1
        for date in occurrences(item, until):
            result.append(
                Upcoming(
                    item_id=item.id,
                    name=item.name,
                    account_id=item.account_id,
                    date=date,
                    amount=sign * item.amount,
                    overdue=date < today - OVERDUE_AFTER,
                )
            )
    return sorted(result, key=lambda u: (u.date, u.name))


@router.get("/recurring/upcoming")
def upcoming(
    user: CurrentUser, db: DbSession, days: int = Query(default=30, ge=1, le=366)
) -> list[Upcoming]:
    """Expected movements from the overdue ones to `days` ahead (forecast)."""
    return _upcoming(db, user, days)


@router.get("/inbox")
def inbox(user: CurrentUser, db: DbSession) -> Inbox:
    """What needs a look: payments the bank never confirmed (a declined payment?) and
    expected movements that have not arrived."""
    unconfirmed = db.scalars(
        select(Transaction)
        .where(
            Transaction.user_id == user.id,
            Transaction.pending.is_(True),
            Transaction.date <= clock.today() - UNCONFIRMED_AFTER,
        )
        .order_by(Transaction.date)
    )
    return Inbox(
        unconfirmed=[TransactionOut.from_model(row) for row in unconfirmed],
        overdue=[u for u in _upcoming(db, user, 0) if u.overdue],
    )

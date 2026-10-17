"""Income, expenses and transfers between own accounts (RF-MOV-01, 03, 04, 15)."""

import datetime as dt
import uuid
from decimal import Decimal
from typing import Literal, Self

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import ColumnElement, Select, Subquery, and_, delete, func, or_, select

from app import clock, recurring
from app.auth.deps import CurrentUser, DbSession
from app.models.accounts import Account
from app.models.transactions import Category, Transaction
from app.models.user import User
from app.ownership import get_owned_or_404
from app.routers.money_types import Money
from app.rules import load_rulebook

router = APIRouter(prefix="/api", tags=["transactions"])

EntryKind = Literal["expense", "income"]
TransactionKind = Literal["expense", "income", "transfer", "adjustment"]

_MAX_TAGS = 10


def _normalise_tags(tags: list[str]) -> list[str]:
    cleaned: list[str] = []
    for tag in tags:
        value = tag.strip().lstrip("#").strip().lower()
        if value and value not in cleaned:
            cleaned.append(value[:40])
    if len(cleaned) > _MAX_TAGS:
        raise ValueError(f"Como mucho {_MAX_TAGS} etiquetas por movimiento.")
    return cleaned


class _Details(BaseModel):
    description: str = Field(default="", max_length=140)
    note: str | None = Field(default=None, max_length=2000)
    tags: list[str] = Field(default_factory=list)

    @field_validator("description")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()

    @field_validator("tags")
    @classmethod
    def _tags(cls, value: list[str]) -> list[str]:
        return _normalise_tags(value)


class TransactionIn(_Details):
    account_id: uuid.UUID
    date: dt.date
    kind: EntryKind
    amount: Money = Field(description="Positive; the sign comes from kind")
    category_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _non_zero(self) -> Self:
        if self.amount == 0:
            raise ValueError("El importe no puede ser cero.")
        return self


class TransactionUpdate(BaseModel):
    account_id: uuid.UUID | None = None
    date: dt.date | None = None
    kind: EntryKind | None = None
    amount: Money | None = None
    category_id: uuid.UUID | None = None
    description: str | None = Field(default=None, max_length=140)
    note: str | None = Field(default=None, max_length=2000)
    tags: list[str] | None = None

    @field_validator("tags")
    @classmethod
    def _tags(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else _normalise_tags(value)


class TransferIn(_Details):
    from_account_id: uuid.UUID
    to_account_id: uuid.UUID
    date: dt.date
    amount: Money

    @model_validator(mode="after")
    def _valid(self) -> Self:
        if self.amount <= 0:
            raise ValueError("El importe de una transferencia debe ser mayor que cero.")
        if self.from_account_id == self.to_account_id:
            raise ValueError("Elige dos cuentas distintas.")
        return self


class TransactionOut(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    date: dt.date
    kind: TransactionKind
    amount: Money = Field(description="Signed: negative leaves the account")
    description: str
    category_id: uuid.UUID | None
    note: str | None
    tags: list[str]
    transfer_id: uuid.UUID | None
    source: str
    pending: bool = Field(description="Captured payment not yet confirmed by a statement")
    created_at: dt.datetime
    balance_after: Money | None = Field(
        default=None, description="Balance of its account right after it (in lists)"
    )

    @classmethod
    def from_model(cls, row: Transaction, balance_after: Decimal | None = None) -> TransactionOut:
        return cls.model_validate(
            {
                "id": row.id,
                "account_id": row.account_id,
                "date": row.date,
                "kind": row.kind,
                "amount": row.amount,
                "description": row.description,
                "category_id": row.category_id,
                "note": row.note,
                "tags": row.tags,
                "transfer_id": row.transfer_id,
                "source": row.source,
                "pending": row.pending,
                "created_at": row.created_at,
                "balance_after": balance_after,
            }
        )


class TransactionPage(BaseModel):
    items: list[TransactionOut]
    total: int = Field(description="Matching transactions, ignoring limit and offset")
    income: Money = Field(description="Sum of income in the matching set")
    expenses: Money = Field(description="Sum of expenses in the matching set (negative)")


class TagCount(BaseModel):
    tag: str
    count: int


def _signed(kind: str, amount: Decimal) -> Decimal:
    return -abs(amount) if kind == "expense" else abs(amount)


def usable_account(db: DbSession, account_id: uuid.UUID, user: User) -> Account:
    account = get_owned_or_404(db, Account, account_id, user)
    if account.archived_at is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "La cuenta está archivada. Desarchívala para añadirle movimientos.",
        )
    return account


def _check_category(db: DbSession, category_id: uuid.UUID | None, kind: str, user: User) -> None:
    if category_id is None:
        return
    category = get_owned_or_404(db, Category, category_id, user)
    if category.kind != kind:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "La categoría es de gastos y el movimiento es un ingreso, o al revés.",
        )


def _pair(db: DbSession, row: Transaction) -> list[Transaction]:
    """Both legs of a transfer, or just the row itself."""
    if row.transfer_id is None:
        return [row]
    return list(db.scalars(select(Transaction).where(Transaction.transfer_id == row.transfer_id)))


# --- Income and expenses ----------------------------------------------------------------------


@router.post("/transactions", status_code=status.HTTP_201_CREATED)
def create_transaction(body: TransactionIn, user: CurrentUser, db: DbSession) -> TransactionOut:
    usable_account(db, body.account_id, user)
    _check_category(db, body.category_id, body.kind, user)
    amount = _signed(body.kind, body.amount)
    category_id = body.category_id
    if category_id is None and body.description:
        # Without a category, the rules may know it (RF-MOV-07).
        category_id = load_rulebook(db, user).category_for(
            body.description, amount, body.account_id
        )
    row = Transaction(
        user_id=user.id,
        account_id=body.account_id,
        date=body.date,
        kind=body.kind,
        amount=amount,
        category_id=category_id,
        description=body.description,
        note=(body.note or "").strip() or None,
        tags=body.tags,
    )
    db.add(row)
    db.flush()
    recurring.fulfil(db, user, [row])
    db.commit()
    return TransactionOut.from_model(row)


@router.get("/transactions/{transaction_id}")
def read_transaction(transaction_id: uuid.UUID, user: CurrentUser, db: DbSession) -> TransactionOut:
    return TransactionOut.from_model(get_owned_or_404(db, Transaction, transaction_id, user))


@router.patch("/transactions/{transaction_id}")
def update_transaction(
    transaction_id: uuid.UUID, body: TransactionUpdate, user: CurrentUser, db: DbSession
) -> TransactionOut:
    row = get_owned_or_404(db, Transaction, transaction_id, user)
    fields = body.model_fields_set

    if row.kind in ("transfer", "adjustment"):
        if fields & {"account_id", "kind", "category_id"}:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "En una transferencia o un ajuste solo se puede cambiar la fecha, el importe y "
                "el texto.",
            )
        for leg in _pair(db, row):
            _apply_shared(leg, body, keep_sign=row.kind == "transfer")
        db.commit()
        return TransactionOut.from_model(row)

    kind = body.kind or row.kind
    if body.account_id is not None:
        usable_account(db, body.account_id, user)
        row.account_id = body.account_id
    category_id = body.category_id if "category_id" in fields else row.category_id
    _check_category(db, category_id, kind, user)
    row.category_id = category_id
    row.kind = kind
    amount = body.amount if body.amount is not None else row.amount
    if amount == 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "El importe no puede ser cero.")
    row.amount = _signed(kind, amount)
    _apply_shared(row, body.model_copy(update={"amount": None}), keep_sign=True)
    db.commit()
    return TransactionOut.from_model(row)


def _apply_shared(leg: Transaction, body: TransactionUpdate, *, keep_sign: bool) -> None:
    """Fields both legs of a transfer share. With keep_sign, each leg keeps its direction and
    only the size of the amount changes; an adjustment takes the amount as given."""
    if body.date is not None:
        leg.date = body.date
    if body.amount is not None:
        if body.amount == 0:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "El importe no puede ser cero."
            )
        size = abs(body.amount)
        leg.amount = (size if leg.amount > 0 else -size) if keep_sign else body.amount
    if body.description is not None:
        leg.description = body.description.strip()
    if "note" in body.model_fields_set:
        leg.note = (body.note or "").strip() or None
    if body.tags is not None:
        leg.tags = body.tags


@router.post("/transactions/{transaction_id}/confirm")
def confirm_transaction(
    transaction_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> TransactionOut:
    """Keep a captured payment that no statement has confirmed (paid in cash back, a bank
    whose statements are not imported...)."""
    row = get_owned_or_404(db, Transaction, transaction_id, user)
    row.pending = False
    db.commit()
    return TransactionOut.from_model(row)


@router.delete("/transactions/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(transaction_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Response:
    """Deleting either leg of a transfer deletes the whole transfer."""
    row = get_owned_or_404(db, Transaction, transaction_id, user)
    for leg in _pair(db, row):
        db.delete(leg)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Bulk edit -------------------------------------------------------------------------------

BulkAction = Literal["categorise", "tag", "untag", "delete"]


class BulkEdit(BaseModel):
    ids: list[uuid.UUID] = Field(min_length=1, max_length=500)
    action: BulkAction
    category_id: uuid.UUID | None = Field(default=None, description="For categorise; null clears")
    tag: str | None = Field(default=None, max_length=40, description="For tag and untag")

    @model_validator(mode="after")
    def _needs(self) -> Self:
        if self.action in ("tag", "untag"):
            tags = _normalise_tags([self.tag or ""])
            if not tags:
                raise ValueError("Escribe la etiqueta.")
            self.tag = tags[0]
        return self


class BulkResult(BaseModel):
    affected: int


@router.post("/transactions/bulk")
def bulk_edit(body: BulkEdit, user: CurrentUser, db: DbSession) -> BulkResult:
    """Recategorise, tag or delete several movements at once (RF-MOV-15).

    Transfers and adjustments have no category: categorising skips them. Deleting a transfer
    deletes both of its movements."""
    rows = list(
        db.scalars(
            select(Transaction).where(
                Transaction.user_id == user.id, Transaction.id.in_(set(body.ids))
            )
        )
    )
    if len(rows) != len(set(body.ids)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Algún movimiento ya no existe.")
    affected = 0
    if body.action == "categorise":
        category = (
            get_owned_or_404(db, Category, body.category_id, user)
            if body.category_id is not None
            else None
        )
        for row in rows:
            if row.kind not in ("expense", "income"):
                continue
            if category is not None and category.kind != row.kind:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    "Has elegido ingresos y gastos a la vez: la categoría solo vale para uno "
                    "de los dos.",
                )
            row.category_id = body.category_id
            affected += 1
    elif body.action == "tag":
        for row in rows:
            if body.tag not in row.tags:
                if len(row.tags) >= _MAX_TAGS:
                    raise HTTPException(
                        status.HTTP_422_UNPROCESSABLE_CONTENT,
                        f"Algún movimiento ya tiene {_MAX_TAGS} etiquetas.",
                    )
                row.tags = [*row.tags, body.tag or ""]
                affected += 1
    elif body.action == "untag":
        for row in rows:
            if body.tag in row.tags:
                row.tags = [tag for tag in row.tags if tag != body.tag]
                affected += 1
    else:
        transfer_ids = {row.transfer_id for row in rows if row.transfer_id is not None}
        doomed = {row.id for row in rows}
        if transfer_ids:
            doomed |= set(
                db.scalars(
                    select(Transaction.id).where(
                        Transaction.user_id == user.id,
                        Transaction.transfer_id.in_(transfer_ids),
                    )
                )
            )
        result = db.execute(
            delete(Transaction).where(Transaction.user_id == user.id, Transaction.id.in_(doomed))
        )
        affected = result.rowcount  # type: ignore[attr-defined]
    db.commit()
    return BulkResult(affected=affected)


# --- Transfers --------------------------------------------------------------------------------


@router.post("/transfers", status_code=status.HTTP_201_CREATED)
def create_transfer(body: TransferIn, user: CurrentUser, db: DbSession) -> list[TransactionOut]:
    """Money moved between own accounts: two linked rows, neither income nor expense."""
    source = usable_account(db, body.from_account_id, user)
    target = usable_account(db, body.to_account_id, user)
    if source.currency != target.currency:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Por ahora las transferencias son entre cuentas de la misma divisa.",
        )
    transfer_id = uuid.uuid4()
    created_at = clock.now()  # one operation: both legs share the moment
    description = body.description or f"Transferencia a {target.name}"
    legs = [
        Transaction(
            user_id=user.id,
            account_id=account.id,
            date=body.date,
            kind="transfer",
            amount=amount,
            description=text,
            note=(body.note or "").strip() or None,
            tags=body.tags,
            transfer_id=transfer_id,
            created_at=created_at,
        )
        for account, amount, text in (
            (source, -body.amount, description),
            (target, body.amount, body.description or f"Transferencia desde {source.name}"),
        )
    ]
    db.add_all(legs)
    db.commit()
    return [TransactionOut.from_model(leg) for leg in legs]


# --- Search -----------------------------------------------------------------------------------


def _filtered(
    user: User,
    account_id: uuid.UUID | None,
    category_id: uuid.UUID | None,
    kind: TransactionKind | None,
    tag: str | None,
    q: str | None,
    date_from: dt.date | None,
    date_to: dt.date | None,
) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = [Transaction.user_id == user.id]
    if account_id:
        conditions.append(Transaction.account_id == account_id)
    if category_id:
        # A main category also matches its subcategories.
        children = select(Category.id).where(
            Category.parent_id == category_id, Category.user_id == user.id
        )
        conditions.append(
            or_(Transaction.category_id == category_id, Transaction.category_id.in_(children))
        )
    if kind:
        conditions.append(Transaction.kind == kind)
    if tag:
        conditions.append(Transaction.tags.contains([tag.strip().lstrip("#").lower()]))
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        conditions.append(
            or_(Transaction.description.ilike(pattern), Transaction.note.ilike(pattern))
        )
    if date_from:
        conditions.append(Transaction.date >= date_from)
    if date_to:
        conditions.append(Transaction.date <= date_to)
    return conditions


def _running_balances(user: User) -> Subquery:
    """Each movement with its account's balance right after it, in the order the list shows
    them (reversed). The opening balance is an anchor (see app/ledger.py): the balance after a
    movement is the anchor plus everything up to it, minus the history before the anchor."""
    account = Transaction.account_id
    up_to_here = func.sum(Transaction.amount).over(
        partition_by=account,
        order_by=(
            Transaction.date,
            Transaction.created_at,
            Transaction.amount.desc(),
            Transaction.id.desc(),
        ),
        rows=(None, 0),
    )
    before_anchor = func.coalesce(
        func.sum(Transaction.amount)
        .filter(Transaction.date < Account.opening_date)
        .over(partition_by=account),
        0,
    )
    return (
        select(
            Transaction.id.label("id"),
            (Account.opening_balance + up_to_here - before_anchor).label("balance_after"),
        )
        .join(Account, Account.id == account)
        .where(Transaction.user_id == user.id)
        .subquery()
    )


@router.get("/transactions")
def list_transactions(
    user: CurrentUser,
    db: DbSession,
    account_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    kind: TransactionKind | None = None,
    tag: str | None = Query(default=None, max_length=40),
    q: str | None = Query(default=None, max_length=100, description="Text in concept or note"),
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> TransactionPage:
    condition = and_(*_filtered(user, account_id, category_id, kind, tag, q, date_from, date_to))
    running = _running_balances(user)
    rows = db.execute(
        select(Transaction, running.c.balance_after)
        .join(running, running.c.id == Transaction.id)
        .where(condition)
        # Same moment (both legs of a transfer): the money leaving comes first.
        .order_by(
            Transaction.date.desc(),
            Transaction.created_at.desc(),
            Transaction.amount,
            Transaction.id,
        )
        .limit(limit)
        .offset(offset)
    )
    total, income, expenses = db.execute(
        select(
            func.count(),
            func.coalesce(func.sum(Transaction.amount).filter(Transaction.kind == "income"), 0),
            func.coalesce(func.sum(Transaction.amount).filter(Transaction.kind == "expense"), 0),
        ).where(condition)
    ).one()
    return TransactionPage(
        items=[TransactionOut.from_model(row, after) for row, after in rows],
        total=total,
        income=Decimal(income),
        expenses=Decimal(expenses),
    )


@router.get("/tags")
def list_tags(user: CurrentUser, db: DbSession) -> list[TagCount]:
    """Tags in use, most used first (for suggestions)."""
    tag = func.unnest(Transaction.tags).label("tag")
    used: Select[tuple[str]] = select(tag).where(Transaction.user_id == user.id)
    sub = used.subquery()
    rows = db.execute(
        select(sub.c.tag, func.count()).group_by(sub.c.tag).order_by(func.count().desc(), sub.c.tag)
    )
    return [TagCount(tag=name, count=count) for name, count in rows]

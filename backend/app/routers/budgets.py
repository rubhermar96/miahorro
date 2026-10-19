"""Budget by financial month, in limits or zero-based mode (RF-PRS-01…04)."""

import datetime as dt
import uuid
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app import budgets, clock
from app.auth.deps import CurrentUser, DbSession
from app.models.transactions import Category
from app.models.user import User
from app.ownership import get_owned_or_404
from app.routers.money_types import Money
from finance.periods import period_of, shift

router = APIRouter(prefix="/api/budget", tags=["budget"])

BudgetMode = Literal["limits", "zero_based"]


class LineOut(BaseModel):
    category_id: uuid.UUID
    assigned: Money = Field(description="Limit (limits) or assigned this month (zero-based)")
    activity: Money = Field(description="Spent (negative) or refunded this month")
    carried: Money = Field(description="Left over (or overspent) from earlier months")
    available: Money = Field(description="carried + assigned + activity")


class BudgetOut(BaseModel):
    mode: BudgetMode | None = Field(description="Null until the user chooses")
    rollover: bool = Field(description="Leftovers carry over (always in zero-based)")
    start: dt.date
    end: dt.date
    previous_start: dt.date
    next_start: dt.date
    lines: list[LineOut]
    unbudgeted: Money = Field(description="Spent in categories without a line, or uncategorised")
    assigned: Money
    activity: Money
    available: Money
    cash: Money | None = Field(description="Zero-based: everyday money minus what goals hold")
    to_assign: Money | None = Field(description="Zero-based: cash not yet in any line")


class AmountIn(BaseModel):
    date: dt.date | None = Field(default=None, description="Any day of the month; today if null")
    amount: Money


class MoveIn(BaseModel):
    date: dt.date | None = None
    from_category_id: uuid.UUID
    to_category_id: uuid.UUID
    amount: Money


class MonthIn(BaseModel):
    date: dt.date | None = None


def _out(db: DbSession, user: User, date: dt.date) -> BudgetOut:
    result = budgets.month(db, user, date)
    lines = [
        LineOut(
            category_id=line.category_id,
            assigned=line.assigned,
            activity=line.activity,
            carried=line.carried,
            available=line.available,
        )
        for line in result.lines
    ]
    return BudgetOut(
        mode=user.budget_mode,
        rollover=user.budget_mode == "zero_based" or user.budget_rollover,
        start=result.start,
        end=result.end,
        previous_start=shift(result.start, -1, user.month_start_day),
        next_start=shift(result.start, 1, user.month_start_day),
        lines=lines,
        unbudgeted=result.unbudgeted,
        assigned=sum((line.assigned for line in result.lines), Decimal(0)),
        activity=sum((line.activity for line in result.lines), Decimal(0)),
        available=sum((line.available for line in result.lines), Decimal(0)),
        cash=result.cash,
        to_assign=result.to_assign,
    )


def _mode(user: User) -> str:
    if user.budget_mode is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Elige antes cómo quieres llevar el presupuesto."
        )
    return user.budget_mode


def _expense_category(db: DbSession, user: User, category_id: uuid.UUID) -> Category:
    category = get_owned_or_404(db, Category, category_id, user)
    if category.kind != "expense":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "El presupuesto es para categorías de gasto; los ingresos van a «Por asignar».",
        )
    return category


@router.get("")
def read_budget(user: CurrentUser, db: DbSession, date: dt.date | None = None) -> BudgetOut:
    """The financial month that contains `date` (today by default)."""
    return _out(db, user, date or clock.today())


@router.put("/lines/{category_id}")
def set_line(category_id: uuid.UUID, body: AmountIn, user: CurrentUser, db: DbSession) -> BudgetOut:
    """Set the limit (from this month on) or what is assigned this month."""
    _mode(user)
    _expense_category(db, user, category_id)
    if body.amount < 0:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "El importe no puede ser negativo."
        )
    date = body.date or clock.today()
    budgets.set_amount(db, user, date, category_id, body.amount)
    db.commit()
    return _out(db, user, date)


@router.delete("/lines/{category_id}")
def remove_line(
    category_id: uuid.UUID, user: CurrentUser, db: DbSession, date: dt.date | None = None
) -> BudgetOut:
    """Limits: no limit from this month on. Zero-based: only an empty line can go."""
    mode = _mode(user)
    date = date or clock.today()
    if mode == "limits":
        budgets.set_amount(db, user, date, category_id, Decimal(0))
    else:
        current = budgets.month(db, user, date)
        line = next((li for li in current.lines if li.category_id == category_id), None)
        if line is not None and line.available != 0:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Esta categoría aún tiene dinero: muévelo antes a otra o a «Por asignar».",
            )
        budgets.remove_line(db, user, category_id)
    db.commit()
    return _out(db, user, date)


@router.post("/move")
def move_money(body: MoveIn, user: CurrentUser, db: DbSession) -> BudgetOut:
    """Zero-based: move available money from one category to another."""
    if _mode(user) != "zero_based":
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Mover dinero entre categorías es del modo base cero."
        )
    if body.amount <= 0 or body.from_category_id == body.to_category_id:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Indica un importe mayor que cero y dos categorías distintas.",
        )
    _expense_category(db, user, body.to_category_id)
    date = body.date or clock.today()
    current = budgets.month(db, user, date)
    source = next((li for li in current.lines if li.category_id == body.from_category_id), None)
    if source is None or source.available < body.amount:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Esa categoría no tiene tanto dinero disponible."
        )
    budgets.add_amount(db, user, date, body.from_category_id, -body.amount)
    budgets.add_amount(db, user, date, body.to_category_id, body.amount)
    db.commit()
    return _out(db, user, date)


@router.post("/copy-previous")
def copy_previous(body: MonthIn, user: CurrentUser, db: DbSession) -> BudgetOut:
    """Zero-based: assign this month what was assigned last month, where nothing is yet."""
    if _mode(user) != "zero_based":
        raise HTTPException(status.HTTP_409_CONFLICT, "Copiar lo asignado es del modo base cero.")
    date = body.date or clock.today()
    start = period_of(date, user.month_start_day)[0]
    previous = shift(start, -1, user.month_start_day)
    for line in budgets.month(db, user, previous).lines:
        if line.assigned > 0 and budgets.month_assigned(db, user, date, line.category_id) == 0:
            budgets.set_amount(db, user, date, line.category_id, line.assigned)
    db.commit()
    return _out(db, user, date)

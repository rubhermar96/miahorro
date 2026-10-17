"""Savings goals (RF-OBJ-01, 02, 03) and the savings rate (RF-OBJ-06)."""

import datetime as dt
import uuid
from decimal import Decimal
from typing import Literal, Self

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app import clock, ledger
from app.auth.deps import CurrentUser, DbSession
from app.goals import (
    GoalStatus,
    pots,
    progress,
    reserved_in,
    savings_periods,
    whole_accounts,
)
from app.models.accounts import Account
from app.models.goals import GoalAccount, GoalContribution, SavingsGoal
from app.models.user import User
from app.ownership import get_owned_or_404, owned
from app.routers.money_types import Money

router = APIRouter(prefix="/api", tags=["goals"])

Priority = Literal[1, 2, 3]


class GoalFields(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    target_amount: Money
    target_date: dt.date | None = None
    priority: Priority = Field(default=2, description="1 high · 2 medium · 3 low")
    icon: str | None = Field(default=None, max_length=8)
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def _tidy(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Ponle un nombre al objetivo.")
        return value

    @field_validator("target_amount")
    @classmethod
    def _positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("El importe del objetivo debe ser mayor que cero.")
        return value


class GoalIn(GoalFields):
    account_ids: list[uuid.UUID] = Field(
        default_factory=list, description="Accounts that belong to the goal entirely"
    )


class GoalUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    target_amount: Money | None = None
    target_date: dt.date | None = None
    priority: Priority | None = None
    icon: str | None = Field(default=None, max_length=8)
    note: str | None = Field(default=None, max_length=2000)
    account_ids: list[uuid.UUID] | None = None
    achieved: bool | None = None


class Pot(BaseModel):
    account_id: uuid.UUID
    amount: Money


class GoalOut(GoalFields):
    id: uuid.UUID
    account_ids: list[uuid.UUID]
    pots: list[Pot] = Field(description="Money set aside in each account")
    achieved: bool
    saved: Money
    remaining: Money
    percent: int
    required_monthly: Money | None = Field(description="To reach the target date")
    pace: Money | None = Field(description="Saved per month lately; null if too recent")
    estimated_date: dt.date | None = Field(description="When it is reached at this pace")
    status: GoalStatus


class ContributionIn(BaseModel):
    account_id: uuid.UUID
    amount: Money = Field(description="Positive")
    action: Literal["add", "withdraw"] = "add"
    date: dt.date | None = None
    note: str | None = Field(default=None, max_length=140)

    @model_validator(mode="after")
    def _positive(self) -> Self:
        if self.amount <= 0:
            raise ValueError("El importe debe ser mayor que cero.")
        return self


class ContributionOut(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    date: dt.date
    amount: Money = Field(description="Positive: set aside · negative: taken back")
    note: str | None


class SavingsPeriod(BaseModel):
    start: dt.date
    end: dt.date
    income: Money
    expenses: Money
    saved: Money
    rate: Decimal | None = Field(description="Percent of income saved; null without income")


class SavingsRate(BaseModel):
    target: int | None = Field(description="Percent to save, from the preferences")
    periods: list[SavingsPeriod] = Field(description="Financial months, oldest first")


def _out(db: DbSession, goal: SavingsGoal, account_ids: list[uuid.UUID]) -> GoalOut:
    accounts = list(db.scalars(select(Account).where(Account.id.in_(account_ids))))
    state = progress(db, goal, accounts, clock.today())
    return GoalOut(
        id=goal.id,
        name=goal.name,
        target_amount=goal.target_amount,
        target_date=goal.target_date,
        priority=goal.priority,
        icon=goal.icon,
        note=goal.note,
        account_ids=account_ids,
        pots=[Pot(account_id=a, amount=v) for a, v in pots(db, goal.id).items()],
        achieved=goal.achieved_at is not None,
        saved=state.saved,
        remaining=state.remaining,
        percent=state.percent,
        required_monthly=state.required_monthly,
        pace=state.pace,
        estimated_date=state.estimated_date,
        status=state.status,
    )


def _link_accounts(
    db: DbSession, user: User, goal: SavingsGoal, account_ids: list[uuid.UUID]
) -> list[uuid.UUID]:
    """Make these accounts belong entirely to the goal (and only these)."""
    wanted = list(dict.fromkeys(account_ids))
    for account_id in wanted:
        account = get_owned_or_404(db, Account, account_id, user)
        others = db.scalar(
            select(GoalContribution.id).where(
                GoalContribution.account_id == account_id, GoalContribution.goal_id != goal.id
            )
        )
        if others is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"«{account.name}» tiene dinero apartado para otros objetivos: no puede ser "
                "entera de este.",
            )
    db.execute(delete(GoalAccount).where(GoalAccount.goal_id == goal.id))
    db.add_all(GoalAccount(goal_id=goal.id, account_id=account_id) for account_id in wanted)
    try:
        db.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Una de esas cuentas ya es entera de otro objetivo."
        ) from exc
    return wanted


def _priority_order(goal: GoalOut) -> tuple[int, int, dt.date, str]:
    return (
        1 if goal.achieved else 0,
        goal.priority,
        goal.target_date or dt.date.max,
        goal.name.lower(),
    )


@router.get("/goals")
def list_goals(user: CurrentUser, db: DbSession) -> list[GoalOut]:
    """Pending goals first, by priority and date."""
    goals = list(db.scalars(owned(SavingsGoal, user)))
    linked = whole_accounts(db, [goal.id for goal in goals])
    return sorted((_out(db, goal, linked[goal.id]) for goal in goals), key=_priority_order)


@router.post("/goals", status_code=status.HTTP_201_CREATED)
def create_goal(body: GoalIn, user: CurrentUser, db: DbSession) -> GoalOut:
    goal = SavingsGoal(
        user_id=user.id,
        name=body.name,
        target_amount=body.target_amount,
        target_date=body.target_date,
        priority=body.priority,
        icon=body.icon or None,
        note=(body.note or "").strip() or None,
        created_at=clock.now(),
    )
    db.add(goal)
    db.flush()
    linked = _link_accounts(db, user, goal, body.account_ids)
    db.commit()
    return _out(db, goal, linked)


@router.get("/goals/{goal_id}")
def read_goal(goal_id: uuid.UUID, user: CurrentUser, db: DbSession) -> GoalOut:
    goal = get_owned_or_404(db, SavingsGoal, goal_id, user)
    return _out(db, goal, whole_accounts(db, [goal.id])[goal.id])


@router.patch("/goals/{goal_id}")
def update_goal(goal_id: uuid.UUID, body: GoalUpdate, user: CurrentUser, db: DbSession) -> GoalOut:
    goal = get_owned_or_404(db, SavingsGoal, goal_id, user)
    fields = body.model_fields_set
    merged = GoalFields(
        name=body.name if body.name is not None else goal.name,
        target_amount=body.target_amount if body.target_amount is not None else goal.target_amount,
        target_date=body.target_date if "target_date" in fields else goal.target_date,
        priority=body.priority or goal.priority,
        icon=body.icon if "icon" in fields else goal.icon,
        note=body.note if "note" in fields else goal.note,
    )
    goal.name, goal.target_amount, goal.target_date = (
        merged.name,
        merged.target_amount,
        merged.target_date,
    )
    goal.priority, goal.icon = merged.priority, merged.icon or None
    goal.note = (merged.note or "").strip() or None
    if body.achieved is not None:
        goal.achieved_at = clock.now() if body.achieved else None
    linked = (
        _link_accounts(db, user, goal, body.account_ids)
        if body.account_ids is not None
        else whole_accounts(db, [goal.id])[goal.id]
    )
    db.commit()
    return _out(db, goal, linked)


@router.delete("/goals/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(goal_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Response:
    """The money set aside is released: it is available again in its accounts."""
    db.delete(get_owned_or_404(db, SavingsGoal, goal_id, user))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Piggy banks ------------------------------------------------------------------------------


@router.get("/goals/{goal_id}/contributions")
def list_contributions(
    goal_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> list[ContributionOut]:
    get_owned_or_404(db, SavingsGoal, goal_id, user)
    rows = db.scalars(
        owned(GoalContribution, user)
        .where(GoalContribution.goal_id == goal_id)
        .order_by(GoalContribution.date.desc(), GoalContribution.created_at.desc())
    )
    return [
        ContributionOut(id=r.id, account_id=r.account_id, date=r.date, amount=r.amount, note=r.note)
        for r in rows
    ]


@router.post("/goals/{goal_id}/contributions", status_code=status.HTTP_201_CREATED)
def add_contribution(
    goal_id: uuid.UUID, body: ContributionIn, user: CurrentUser, db: DbSession
) -> GoalOut:
    """Set money aside for the goal inside an account, or take it back. Only what is
    available can be set aside: the balance minus what other goals already hold."""
    goal = get_owned_or_404(db, SavingsGoal, goal_id, user)
    account = get_owned_or_404(db, Account, body.account_id, user)
    owner = db.scalar(select(GoalAccount.goal_id).where(GoalAccount.account_id == account.id))
    if owner is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"«{account.name}» ya es entera de un objetivo: todo su saldo cuenta para él.",
        )
    if body.action == "add":
        available = ledger.balance_of(db, account) - reserved_in(db, user, account)
        if body.amount > available:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"En «{account.name}» solo hay {_es(available)} € disponibles para apartar.",
            )
        amount = body.amount
    else:
        in_pot = pots(db, goal.id).get(account.id, Decimal(0))
        if body.amount > in_pot:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"En «{account.name}» este objetivo solo tiene {_es(in_pot)} € apartados.",
            )
        amount = -body.amount
    db.add(
        GoalContribution(
            user_id=user.id,
            goal_id=goal.id,
            account_id=account.id,
            date=body.date or clock.today(),
            amount=amount,
            note=(body.note or "").strip() or None,
            created_at=clock.now(),
        )
    )
    db.commit()
    return _out(db, goal, whole_accounts(db, [goal.id])[goal.id])


@router.delete(
    "/goals/{goal_id}/contributions/{contribution_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_contribution(
    goal_id: uuid.UUID, contribution_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> Response:
    row = get_owned_or_404(db, GoalContribution, contribution_id, user)
    if row.goal_id != goal_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Savings rate -----------------------------------------------------------------------------


@router.get("/savings-rate")
def savings_rate(
    user: CurrentUser, db: DbSession, months: int = Query(default=6, ge=1, le=24)
) -> SavingsRate:
    """Income, expenses and the share saved in each financial month (from the payday set in
    the preferences)."""
    periods = savings_periods(db, user, clock.today(), months)
    return SavingsRate(
        target=user.savings_rate_target,
        periods=[
            SavingsPeriod(
                start=p.start,
                end=p.end,
                income=p.income,
                expenses=p.expenses,
                saved=p.saved,
                rate=p.rate,
            )
            for p in periods
        ],
    )


def _es(amount: Decimal) -> str:
    return f"{amount:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")

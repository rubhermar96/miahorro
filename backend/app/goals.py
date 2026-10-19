"""Savings goals and the savings rate (RF-OBJ-01…03, 06): what is saved, what is reserved in
each account, the pace and the forecast."""

import datetime as dt
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import ledger
from app.models.accounts import Account
from app.models.goals import GoalAccount, GoalContribution, SavingsGoal
from app.models.transactions import Transaction
from app.models.user import User
from finance.goals import estimated_date, monthly_pace, required_monthly
from finance.money import round_cents
from finance.periods import last_periods

# The pace is what the goal grew in this window (or since it was created, if later).
PACE_WINDOW = dt.timedelta(days=90)

type GoalStatus = Literal["achieved", "on_track", "behind", "starting", "no_date"]


def whole_accounts(db: Session, goal_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[uuid.UUID]]:
    """Goal → accounts it owns entirely."""
    result: dict[uuid.UUID, list[uuid.UUID]] = {goal_id: [] for goal_id in goal_ids}
    rows = db.execute(
        select(GoalAccount.goal_id, GoalAccount.account_id).where(GoalAccount.goal_id.in_(goal_ids))
    )
    for goal_id, account_id in rows:
        result[goal_id].append(account_id)
    return result


def pots(db: Session, goal_id: uuid.UUID) -> dict[uuid.UUID, Decimal]:
    """Account → money set aside in it for this goal."""
    rows = db.execute(
        select(GoalContribution.account_id, func.sum(GoalContribution.amount))
        .where(GoalContribution.goal_id == goal_id)
        .group_by(GoalContribution.account_id)
    )
    return {account_id: Decimal(total) for account_id, total in rows if total}


def reserved_by_account(db: Session, user: User) -> dict[uuid.UUID, Decimal]:
    """Money in each account that belongs to goals: what is set aside in piggy banks, or
    everything, for accounts a goal owns whole."""
    reserved: dict[uuid.UUID, Decimal] = {}
    rows = db.execute(
        select(GoalContribution.account_id, func.sum(GoalContribution.amount))
        .where(GoalContribution.user_id == user.id)
        .group_by(GoalContribution.account_id)
    )
    for account_id, total in rows:
        reserved[account_id] = Decimal(total)
    whole = db.scalars(
        select(GoalAccount.account_id)
        .join(SavingsGoal, SavingsGoal.id == GoalAccount.goal_id)
        .where(SavingsGoal.user_id == user.id)
    ).all()
    if whole:
        totals = ledger.transaction_totals(db, user)
        for account in db.scalars(select(Account).where(Account.id.in_(whole))):
            reserved[account.id] = account.opening_balance + totals.get(account.id, Decimal(0))
    return reserved


def reserved_in(db: Session, user: User, account: Account) -> Decimal:
    return reserved_by_account(db, user).get(account.id, Decimal(0))


def saved_on(db: Session, goal: SavingsGoal, accounts: list[Account], on: dt.date) -> Decimal:
    """What the goal had at the end of a day."""
    set_aside = db.scalar(
        select(func.coalesce(func.sum(GoalContribution.amount), 0)).where(
            GoalContribution.goal_id == goal.id, GoalContribution.date <= on
        )
    )
    whole = sum((ledger.balance_on(db, account, on) for account in accounts), Decimal(0))
    return Decimal(set_aside or 0) + whole


@dataclass(frozen=True)
class Progress:
    saved: Decimal
    remaining: Decimal
    percent: int
    required_monthly: Decimal | None
    pace: Decimal | None
    estimated_date: dt.date | None
    status: GoalStatus


def progress(db: Session, goal: SavingsGoal, accounts: list[Account], today: dt.date) -> Progress:
    saved = saved_on(db, goal, accounts, today)
    remaining = max(goal.target_amount - saved, Decimal(0))
    percent = min(int(saved * 100 / goal.target_amount), 100) if saved > 0 else 0

    # Pace: growth over the last months. Without whole accounts the history starts when the
    # goal was created, and what was put in that first day is the starting point, not pace.
    start = today - PACE_WINDOW
    if not accounts:
        start = max(start, goal.created_at.date())
    pace = monthly_pace(saved - saved_on(db, goal, accounts, start), start, today)

    required = required_monthly(remaining, today, goal.target_date) if goal.target_date else None
    if goal.achieved_at is not None or remaining == 0:
        status: GoalStatus = "achieved"
    elif goal.target_date is None:
        status = "no_date"
    elif pace is None:
        status = "starting"
    else:
        status = "on_track" if required is not None and pace >= required else "behind"
    return Progress(
        saved=round_cents(saved),
        remaining=round_cents(remaining),
        percent=percent,
        required_monthly=required,
        pace=pace,
        estimated_date=estimated_date(remaining, pace, today),
        status=status,
    )


# --- Savings rate -----------------------------------------------------------------------------


@dataclass(frozen=True)
class Period:
    start: dt.date
    end: dt.date
    income: Decimal
    expenses: Decimal  # negative

    @property
    def saved(self) -> Decimal:
        return self.income + self.expenses

    @property
    def rate(self) -> Decimal | None:
        """Percent of income saved; None without income."""
        if self.income <= 0:
            return None
        return (self.saved * 100 / self.income).quantize(Decimal("0.1"))


def savings_periods(db: Session, user: User, today: dt.date, count: int) -> list[Period]:
    """Income and expenses per financial month. Transfers between own accounts and balance
    adjustments are neither, so they never count."""
    result = []
    for start, end in last_periods(today, user.month_start_day, count):
        income, expenses = db.execute(
            select(
                func.coalesce(func.sum(Transaction.amount).filter(Transaction.kind == "income"), 0),
                func.coalesce(
                    func.sum(Transaction.amount).filter(Transaction.kind == "expense"), 0
                ),
            ).where(Transaction.user_id == user.id, Transaction.date.between(start, end))
        ).one()
        result.append(Period(start, end, Decimal(income), Decimal(expenses)))
    return result

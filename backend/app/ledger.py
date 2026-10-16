"""Balances and rates derived from the stored data. Balances are never stored: they are the
opening balance plus every transaction, so they cannot drift."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.accounts import Account, AccountRate
from app.models.transactions import Transaction
from app.models.user import User


def transaction_totals(db: Session, user: User) -> dict[uuid.UUID, Decimal]:
    """Sum of transactions per account, for all of a user's accounts at once."""
    rows = db.execute(
        select(Transaction.account_id, func.sum(Transaction.amount))
        .where(Transaction.user_id == user.id)
        .group_by(Transaction.account_id)
    )
    return {account_id: Decimal(total) for account_id, total in rows}


def balance_of(db: Session, account: Account) -> Decimal:
    total = db.scalar(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.account_id == account.id
        )
    )
    return account.opening_balance + Decimal(total or 0)


def rate_on(account: Account, on: date) -> AccountRate | None:
    """The remuneration in force on a date (the latest one that had started)."""
    current = None
    for rate in account.rates:  # ordered by valid_from
        if rate.valid_from <= on:
            current = rate
    return current

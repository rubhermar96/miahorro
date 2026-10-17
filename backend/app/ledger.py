"""Balances and rates derived from the stored data. Balances are never stored: they are the
opening balance plus the transactions, so they cannot drift.

The opening balance is an anchor: what the account held when its opening date began.
Transactions from that date on move the balance; older ones (typically imported history) are
already inside the opening balance, so they only matter for balances on earlier dates, which are
worked out backwards from the anchor.
"""

import datetime as dt
import uuid
from collections.abc import Iterable
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.accounts import Account, AccountRate
from app.models.transactions import Transaction
from app.models.user import User


def transaction_totals(db: Session, user: User) -> dict[uuid.UUID, Decimal]:
    """Sum of the transactions that move each account's balance, for all accounts at once."""
    rows = db.execute(
        select(Transaction.account_id, func.sum(Transaction.amount))
        .join(Account, Account.id == Transaction.account_id)
        .where(Transaction.user_id == user.id, Transaction.date >= Account.opening_date)
        .group_by(Transaction.account_id)
    )
    return {account_id: Decimal(total) for account_id, total in rows}


def balance_of(db: Session, account: Account) -> Decimal:
    """The current balance."""
    total = db.scalar(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.account_id == account.id, Transaction.date >= account.opening_date
        )
    )
    return account.opening_balance + Decimal(total or 0)


def balance_on(
    db: Session,
    account: Account,
    on: dt.date,
    extra: Iterable[tuple[dt.date, Decimal]] = (),
) -> Decimal:
    """The balance at the end of a day. `extra` adds movements not stored yet (an import being
    previewed)."""
    anchor = account.opening_date
    day = dt.timedelta(days=1)
    if on >= anchor:
        first, last, sign = anchor, on, 1
    else:
        # Before the anchor: undo what happened after that day and before the opening date.
        first, last, sign = on + day, anchor - day, -1
    stored = db.scalar(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.account_id == account.id, Transaction.date.between(first, last)
        )
    )
    added = sum((amount for date, amount in extra if first <= date <= last), Decimal(0))
    return account.opening_balance + sign * (Decimal(stored or 0) + added)


def rate_on(account: Account, on: dt.date) -> AccountRate | None:
    """The remuneration in force on a date (the latest one that had started)."""
    current = None
    for rate in account.rates:  # ordered by valid_from
        if rate.valid_from <= on:
            current = rate
    return current

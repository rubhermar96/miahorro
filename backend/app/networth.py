"""Net worth on any date (RF-INF-02, RF-PRE-09): accounts plus investments plus what others
owe, minus what is owed on loans. Nothing is stored; each date is worked out from the data.

An account counts from the first day the app knows about it: its opening date, or its oldest
movement if older history was imported. Before that its balance is unknown, so it is left out
instead of guessing. Loans count from the day they were signed. Homes and cars are not assets
yet (RF-INV-09 comes later), so a mortgage weighs in full.
"""

import datetime as dt
import uuid
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import investments, ledger, loans
from app.models.accounts import Account
from app.models.loans import Loan
from app.models.transactions import Transaction
from app.models.user import User
from app.ownership import owned
from finance.loans import Installment, Prepayment
from finance.money import round_cents

_ZERO = Decimal("0.00")


@dataclass(frozen=True)
class NetWorth:
    date: dt.date
    accounts: Decimal  # in the main currency; cards in debt count negative
    investments: Decimal  # what has a price
    lent: Decimal  # what others owe the user
    debts: Decimal  # capital left on the user's loans, positive
    other_currencies: dict[str, Decimal] = field(default_factory=dict)

    @property
    def total(self) -> Decimal:
        return self.accounts + self.investments + self.lent - self.debts


class NetWorthBook:
    """Everything needed to value the user's wealth, loaded once and asked for any date."""

    def __init__(self, db: Session, user: User, today: dt.date) -> None:
        self._db = db
        self._user = user
        self._currency = user.currency
        self._accounts = list(db.scalars(owned(Account, user)))
        first_moves: dict[uuid.UUID, dt.date] = {
            account_id: first
            for account_id, first in db.execute(
                select(Transaction.account_id, func.min(Transaction.date))
                .where(Transaction.user_id == user.id)
                .group_by(Transaction.account_id)
            )
        }
        self._known_from: dict[uuid.UUID, dt.date] = {
            a.id: min(a.opening_date, first_moves.get(a.id, a.opening_date)) for a in self._accounts
        }
        self._loans: list[tuple[Loan, list[Installment], list[Prepayment]]] = []
        for loan in db.scalars(owned(Loan, user)):
            rows, _ = loans.table(db, loan, today)
            self._loans.append((loan, rows, loans.prepayments_of(db, loan)))
        self._operations = investments.operations_of(db, user)

    def start(self) -> dt.date | None:
        """The first date anything is known about."""
        dates = [
            *self._known_from.values(),
            *(loan.signed_on for loan, _, _ in self._loans),
            *(op.date for op in self._operations),
        ]
        return min(dates) if dates else None

    def at(self, on: dt.date) -> NetWorth:
        accounts = _ZERO
        others: dict[str, Decimal] = {}
        for account in self._accounts:
            if on < self._known_from[account.id]:
                continue
            balance = ledger.balance_on(self._db, account, on)
            if account.currency == self._currency:
                accounts += balance
            else:
                others[account.currency] = others.get(account.currency, _ZERO) + balance

        lent = debts = _ZERO
        for loan, rows, prepaid in self._loans:
            if on < loan.signed_on:
                continue
            left = loans.summarize(loan, rows, prepaid, on).outstanding
            if loan.kind == "p2p_lent":
                lent += left
            else:
                debts += left

        return NetWorth(
            date=on,
            accounts=accounts,
            investments=self._portfolio(on),
            lent=lent,
            debts=debts,
            other_currencies={code: total for code, total in others.items() if total},
        )

    def _portfolio(self, on: dt.date) -> Decimal:
        rows = [op for op in self._operations if op.date <= on]
        if not rows:
            return _ZERO
        held = investments.holdings(self._db, self._user, rows)
        prices = investments.latest_prices(self._db, self._user, on)
        total = _ZERO
        for investment_id, holding in held.items():
            price = prices.get(investment_id)
            if price is not None and price.value is not None:
                total += round_cents(holding.units * price.value)
        return total


def month_ends(start: dt.date, end: dt.date) -> list[dt.date]:
    """The last day of every month from `start`'s to `end`'s, then `end` itself if it is not
    one already."""
    points: list[dt.date] = []
    year, month = start.year, start.month
    while True:
        following = dt.date(year + month // 12, month % 12 + 1, 1)
        last = following - dt.timedelta(days=1)
        if last >= end:
            break
        if last >= start:
            points.append(last)
        year, month = following.year, following.month
    points.append(end)
    return points

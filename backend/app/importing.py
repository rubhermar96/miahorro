"""Bring statement rows into an account without counting anything twice (RF-IMP-01,
RF-MOV-09, RF-MOV-04). One engine reconciles the sources:

- Already imported: each imported movement keeps a fingerprint of the bank's row (date, amount,
  concept). An overlapping file is recognised row by row, even when the same purchase appears
  twice on one day: the second identical row only counts as known if the account has two.
- Match: the row is a movement already recorded another way (an Apple Pay capture, one
  entered by hand, a transfer leg): same amount, a few days apart. It is merged into it.
- Transfer: the row is money moved to or from another own account, because a rule says so or
  because that account has the opposite amount on a close date. It becomes a transfer.
"""

import datetime as dt
import hashlib
import uuid
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app import clock, recurring
from app.models.accounts import Account
from app.models.imports import ImportBatch
from app.models.transactions import Transaction
from app.models.user import User
from app.rules import Rulebook
from importers.statement import StatementRow
from importers.values import plain

# A movement entered by hand or captured usually appears in the bank a few days later.
MATCH_WINDOW = dt.timedelta(days=4)
# The two sides of a transfer between banks.
TRANSFER_WINDOW = dt.timedelta(days=3)

type RowStatus = Literal["new", "duplicate", "match", "transfer"]
type Decision = Literal["import", "merge", "transfer", "skip"]

# What each kind of row allows, the first being what happens unless the user changes it.
DECISIONS: dict[RowStatus, tuple[Decision, ...]] = {
    "new": ("import", "skip"),
    "duplicate": ("skip", "import"),
    "match": ("merge", "import", "skip"),
    "transfer": ("transfer", "import", "skip"),
}


@dataclass(frozen=True)
class ClassifiedRow:
    row: StatementRow
    key: str
    status: RowStatus
    category_id: uuid.UUID | None
    match_id: uuid.UUID | None  # movement to merge with, or the other side of a transfer
    transfer_account_id: uuid.UUID | None  # the other account of a transfer


def import_key(row: StatementRow) -> str:
    concept = " ".join(plain(row.description).split())
    raw = f"{row.date.isoformat()}|{row.amount}|{concept}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _similarity(a: str, b: str) -> int:
    """Words in common, to prefer the right candidate among several with the same amount."""
    return len(set(plain(a).split()) & set(plain(b).split()))


def classify(
    db: Session, account: Account, rows: list[StatementRow], rulebook: Rulebook
) -> list[ClassifiedRow]:
    keys = [import_key(row) for row in rows]
    counts = db.execute(
        select(Transaction.import_key, func.count())
        .where(Transaction.account_id == account.id, Transaction.import_key.in_(set(keys)))
        .group_by(Transaction.import_key)
    )
    known = {key: count for key, count in counts}
    recorded = _recorded_elsewhere(db, account, rows)
    other_side = _other_accounts(db, account, rows)
    claimed: set[uuid.UUID] = set()
    seen: Counter[str] = Counter()
    result: list[ClassifiedRow] = []
    for row, key in zip(rows, keys, strict=True):
        seen[key] += 1
        category_id = rulebook.category_for(row.description, row.amount, account.id)
        if seen[key] <= known.get(key, 0):
            result.append(ClassifiedRow(row, key, "duplicate", category_id, None, None))
            continue
        match = _best(
            (
                candidate
                for candidate in recorded
                if candidate.id not in claimed
                and candidate.amount == row.amount
                and abs(candidate.date - row.date) <= MATCH_WINDOW
            ),
            row,
        )
        if match is not None:
            claimed.add(match.id)
            result.append(ClassifiedRow(row, key, "match", match.category_id, match.id, None))
            continue
        target = rulebook.transfer_for(row.description, row.amount, account.id)
        pair = _best(
            (
                candidate
                for candidate in other_side
                if candidate.id not in claimed
                and candidate.amount == -row.amount
                and abs(candidate.date - row.date) <= TRANSFER_WINDOW
                and (target is None or candidate.account_id == target)
            ),
            row,
        )
        if pair is not None:
            claimed.add(pair.id)
            target = pair.account_id
        if target is not None:
            result.append(
                ClassifiedRow(row, key, "transfer", None, pair.id if pair else None, target)
            )
        else:
            result.append(ClassifiedRow(row, key, "new", category_id, None, None))
    return result


def _best(candidates: Iterable[Transaction], row: StatementRow) -> Transaction | None:
    """Most words in common with the concept first, then the closest date."""
    return min(
        candidates,
        key=lambda c: (-_similarity(c.description, row.description), abs(c.date - row.date)),
        default=None,
    )


def _window(rows: list[StatementRow], margin: dt.timedelta) -> tuple[dt.date, dt.date]:
    return min(r.date for r in rows) - margin, max(r.date for r in rows) + margin


def _recorded_elsewhere(
    db: Session, account: Account, rows: list[StatementRow]
) -> list[Transaction]:
    """Movements of the account that no statement has confirmed yet: captured, entered by
    hand, transfer legs."""
    if not rows:
        return []
    start, end = _window(rows, MATCH_WINDOW)
    return list(
        db.scalars(
            select(Transaction)
            .where(
                Transaction.account_id == account.id,
                Transaction.import_key.is_(None),
                Transaction.kind != "adjustment",
                Transaction.date.between(start, end),
            )
            .order_by(Transaction.date, Transaction.created_at)
        )
    )


def _other_accounts(db: Session, account: Account, rows: list[StatementRow]) -> list[Transaction]:
    """Plain income and expenses in the user's other accounts (same currency) that could be
    the other side of a transfer."""
    if not rows:
        return []
    start, end = _window(rows, TRANSFER_WINDOW)
    return list(
        db.scalars(
            select(Transaction)
            .join(Account, Account.id == Transaction.account_id)
            .where(
                Transaction.user_id == account.user_id,
                Transaction.account_id != account.id,
                Account.currency == account.currency,
                Transaction.kind.in_(("expense", "income")),
                Transaction.date.between(start, end),
            )
            .order_by(Transaction.date, Transaction.created_at)
        )
    )


def save_import(
    db: Session,
    user: User,
    account: Account,
    rows: list[tuple[ClassifiedRow, Decision]],
    *,
    filename: str,
    template_name: str | None,
    newest_first: bool,
) -> ImportBatch:
    """Apply the decision taken for each row; every change is linked to one batch so the
    whole import can be undone."""
    acted = [(item, decision) for item, decision in rows if decision != "skip"]
    batch = ImportBatch(
        user_id=user.id,
        account_id=account.id,
        filename=filename[:200],
        template_name=template_name,
        imported=sum(1 for _, decision in acted if decision != "merge"),
        merged=sum(1 for _, decision in acted if decision == "merge"),
        skipped=len(rows) - len(acted),
        date_from=min((item.row.date for item, _ in acted), default=None),
        date_to=max((item.row.date for item, _ in acted), default=None),
        created_at=clock.now(),
    )
    db.add(batch)
    db.flush()
    # Movements of the same day keep the bank's order: the list shows the latest first.
    chronological = list(reversed(acted)) if newest_first else acted
    start = clock.now()
    touched: list[Transaction] = []
    for step, (item, decision) in enumerate(chronological):
        moment = start + dt.timedelta(microseconds=step)
        if decision == "merge" and item.match_id is not None:
            existing = db.get(Transaction, item.match_id)
            if existing is not None and existing.account_id == account.id:
                existing.import_key = item.key
                existing.merged_import_id = batch.id
                existing.pending = False
                continue
        row = _new_movement(user, account, item, batch, moment)
        db.add(row)
        touched.append(row)
        if decision == "transfer" and item.transfer_account_id is not None:
            _make_transfer(db, user, account, row, item, batch)
    db.flush()
    recurring.fulfil(db, user, touched)
    return batch


def _new_movement(
    user: User, account: Account, item: ClassifiedRow, batch: ImportBatch, moment: dt.datetime
) -> Transaction:
    return Transaction(
        user_id=user.id,
        account_id=account.id,
        date=item.row.date,
        amount=item.row.amount,
        kind="expense" if item.row.amount < 0 else "income",
        description=item.row.description,
        category_id=item.category_id,
        tags=[],
        source="import",
        import_id=batch.id,
        import_key=item.key,
        created_at=moment,
    )


def _make_transfer(
    db: Session,
    user: User,
    account: Account,
    row: Transaction,
    item: ClassifiedRow,
    batch: ImportBatch,
) -> None:
    """Turn the new row and its other side into the two legs of a transfer. If the other
    account has no matching movement yet, its leg is created (and goes away with an undo)."""
    transfer_id = uuid.uuid4()
    row.kind, row.category_id, row.transfer_id = "transfer", None, transfer_id
    other = db.get(Transaction, item.match_id) if item.match_id else None
    if other is not None:
        other.kind, other.category_id, other.transfer_id = "transfer", None, transfer_id
        other.paired_import_id = batch.id
        return
    target = db.get(Account, item.transfer_account_id)
    if target is None or target.user_id != user.id:
        row.kind, row.transfer_id = "expense" if row.amount < 0 else "income", None
        return
    preposition = "desde" if row.amount < 0 else "a"
    db.add(
        Transaction(
            user_id=user.id,
            account_id=target.id,
            date=row.date,
            amount=-row.amount,
            kind="transfer",
            transfer_id=transfer_id,
            description=f"Transferencia {preposition} {account.name}"[:140],
            tags=[],
            source="import",
            import_id=batch.id,
            created_at=row.created_at,
        )
    )


def undo_import(db: Session, user: User, batch: ImportBatch) -> None:
    """Delete what the import created and put back what it changed."""
    mine = Transaction.user_id == user.id
    # Merged movements become unconfirmed again.
    for row in db.scalars(
        select(Transaction).where(mine, Transaction.merged_import_id == batch.id)
    ):
        row.import_key = None
        row.merged_import_id = None
        row.pending = row.source == "capture"
    # Movements turned into a transfer leg go back to plain income or expense.
    for row in db.scalars(
        select(Transaction).where(mine, Transaction.paired_import_id == batch.id)
    ):
        row.kind = "expense" if row.amount < 0 else "income"
        row.transfer_id = None
        row.paired_import_id = None
    db.flush()
    db.execute(delete(Transaction).where(mine, Transaction.import_id == batch.id))
    db.delete(batch)

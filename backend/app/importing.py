"""Bring statement rows into an account without duplicates (RF-IMP-01).

Each imported movement keeps a fingerprint of the bank's row (date, amount, concept). A later
file that overlaps the earlier one is recognised row by row, even when the same purchase
appears twice on one day: the second identical row only counts as known if the account
already has two.
"""

import datetime as dt
import hashlib
import uuid
from collections import Counter
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import clock
from app.models.accounts import Account
from app.models.imports import ImportBatch
from app.models.transactions import Transaction
from app.models.user import User
from app.rules import Rulebook
from importers.statement import StatementRow
from importers.values import plain

# A movement entered by hand usually appears in the bank a few days later.
MATCH_WINDOW = dt.timedelta(days=4)

type RowStatus = Literal["new", "duplicate", "possible_duplicate"]


@dataclass(frozen=True)
class ClassifiedRow:
    row: StatementRow
    key: str
    status: RowStatus
    category_id: uuid.UUID | None
    match_id: uuid.UUID | None  # the movement it may repeat


def import_key(row: StatementRow) -> str:
    concept = " ".join(plain(row.description).split())
    raw = f"{row.date.isoformat()}|{row.amount}|{concept}"
    return hashlib.sha256(raw.encode()).hexdigest()


def classify(
    db: Session, account: Account, rows: list[StatementRow], rulebook: Rulebook
) -> list[ClassifiedRow]:
    """Which rows are new, which were imported before, and which may repeat a movement
    entered by hand (same amount, a few days apart)."""
    keys = [import_key(row) for row in rows]
    counts = db.execute(
        select(Transaction.import_key, func.count())
        .where(Transaction.account_id == account.id, Transaction.import_key.in_(set(keys)))
        .group_by(Transaction.import_key)
    )
    known = {key: count for key, count in counts}
    candidates = _manual_candidates(db, account, rows)
    claimed: set[uuid.UUID] = set()
    seen: Counter[str] = Counter()
    result: list[ClassifiedRow] = []
    for row, key in zip(rows, keys, strict=True):
        seen[key] += 1
        category_id = rulebook.category_for(row.description, row.amount, account.id)
        if seen[key] <= known.get(key, 0):
            result.append(ClassifiedRow(row, key, "duplicate", category_id, None))
            continue
        match = next(
            (
                candidate
                for candidate in candidates
                if candidate.id not in claimed
                and candidate.amount == row.amount
                and abs(candidate.date - row.date) <= MATCH_WINDOW
            ),
            None,
        )
        if match is not None:
            claimed.add(match.id)
            result.append(ClassifiedRow(row, key, "possible_duplicate", category_id, match.id))
        else:
            result.append(ClassifiedRow(row, key, "new", category_id, None))
    return result


def _manual_candidates(
    db: Session, account: Account, rows: list[StatementRow]
) -> list[Transaction]:
    """Movements not imported from a file (entered by hand, transfers), around the file's dates,
    closest dates first."""
    if not rows:
        return []
    start = min(row.date for row in rows) - MATCH_WINDOW
    end = max(row.date for row in rows) + MATCH_WINDOW
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


def save_import(
    db: Session,
    user: User,
    account: Account,
    rows: list[ClassifiedRow],
    *,
    filename: str,
    template_name: str | None,
    skipped: int,
    newest_first: bool,
) -> ImportBatch:
    """Create the movements of the chosen rows, all linked to one batch."""
    batch = ImportBatch(
        user_id=user.id,
        account_id=account.id,
        filename=filename[:200],
        template_name=template_name,
        imported=len(rows),
        skipped=skipped,
        date_from=min((item.row.date for item in rows), default=None),
        date_to=max((item.row.date for item in rows), default=None),
        created_at=clock.now(),
    )
    db.add(batch)
    db.flush()
    # Movements of the same day keep the bank's order: the list shows the latest first.
    chronological = list(reversed(rows)) if newest_first else rows
    start = clock.now()
    for step, item in enumerate(chronological):
        db.add(
            Transaction(
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
                created_at=start + dt.timedelta(microseconds=step),
            )
        )
    return batch

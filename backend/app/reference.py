"""Reference tables (RF-PLT-02): the value in force on a date, read as a rate or a scale, and
loading the starting values."""

import datetime as dt
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.calculators import ReferenceValue
from app.reference_data import SEED
from finance.taxes import Bracket


class ReferenceDataError(LookupError):
    """A value is missing or badly written in the reference tables."""


def in_force(db: Session, table: str, on: dt.date) -> dict[str, ReferenceValue]:
    """Each key of `table` with its latest value whose `valid_from` is not after `on`."""
    rows = db.scalars(
        select(ReferenceValue)
        .where(ReferenceValue.table_name == table, ReferenceValue.valid_from <= on)
        .order_by(ReferenceValue.key, ReferenceValue.valid_from)
    )
    return {row.key: row for row in rows}


def get(db: Session, table: str, key: str, on: dt.date) -> ReferenceValue:
    row = in_force(db, table, on).get(key)
    if row is None:
        raise ReferenceDataError(
            f"Falta el valor «{key}» de la tabla «{table}» en las tablas de referencia: "
            "añádelo en /admin."
        )
    return row


def brackets(row: ReferenceValue) -> list[Bracket]:
    """The scale of a row, or its single rate as a one-tranche scale."""
    scale = (row.extra or {}).get("brackets")
    if not scale:
        return [Bracket(None, row.value)]
    try:
        result = [
            Bracket(
                None if item["up_to"] is None else Decimal(str(item["up_to"])),
                Decimal(str(item["rate"])),
            )
            for item in scale
        ]
    except (KeyError, TypeError, InvalidOperation) as exc:
        raise ReferenceDataError(
            f"La escala de «{row}» está mal escrita: revísala en /admin."
        ) from exc
    if result[-1].up_to is not None:
        raise ReferenceDataError(f"El último tramo de «{row}» debe quedar abierto (up_to: null).")
    return result


def is_marginal(row: ReferenceValue) -> bool:
    return bool((row.extra or {}).get("marginal", True))


def sync(db: Session) -> int:
    """Add the starting values that are missing; never change the ones already there."""
    existing = {
        (table, key, valid_from)
        for table, key, valid_from in db.execute(
            select(ReferenceValue.table_name, ReferenceValue.key, ReferenceValue.valid_from)
        )
    }
    added = 0
    for seed in SEED:
        if (seed.table, seed.key, seed.valid_from) in existing:
            continue
        db.add(
            ReferenceValue(
                table_name=seed.table,
                key=seed.key,
                value=seed.amount,
                extra=seed.extra,
                valid_from=seed.valid_from,
                source=seed.source,
                note=seed.note,
            )
        )
        added += 1
    db.commit()
    return added

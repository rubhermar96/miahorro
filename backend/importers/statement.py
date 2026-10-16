"""From a table to statement rows: find the header, map the columns, read each row."""

import datetime as dt
import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, Field, model_validator

from finance.money import round_cents
from importers.table import Table
from importers.values import (
    Cell,
    DateOrder,
    cell_text,
    detect_date_order,
    detect_decimal_comma,
    looks_like_date,
    parse_amount,
    parse_date,
    plain,
)

MAX_DESCRIPTION = 140
_HEADER_SEARCH = 60


class StatementError(ValueError):
    """The table does not fit the mapping; the message is for the user."""


class Mapping(BaseModel):
    """Where each field is, by column title, so the rows above the table may vary."""

    date: str = Field(max_length=80)
    description: list[str] = Field(min_length=1, max_length=3)
    amount: str | None = Field(default=None, max_length=80)
    debit: str | None = Field(
        default=None, max_length=80, description="Money out written as positive (Cargo, Debe)"
    )
    credit: str | None = Field(
        default=None, max_length=80, description="Money in written as positive (Abono, Haber)"
    )
    balance: str | None = Field(default=None, max_length=80)
    date_order: DateOrder | None = Field(default=None, description="None: detect it")
    decimal_comma: bool | None = Field(default=None, description="None: detect it")
    invert_sign: bool = Field(default=False, description="Expenses come as positive amounts")

    @model_validator(mode="after")
    def _one_way_for_amounts(self) -> Self:
        if self.amount is None and self.debit is None and self.credit is None:
            raise ValueError("Indica la columna del importe, o las de cargos y abonos.")
        if self.amount is not None and (self.debit is not None or self.credit is not None):
            raise ValueError("Usa una columna de importe o las de cargos y abonos, no ambas.")
        return self

    def columns(self) -> list[str]:
        named = [self.date, *self.description, self.amount, self.debit, self.credit, self.balance]
        return [name for name in named if name is not None]


@dataclass(frozen=True)
class StatementRow:
    number: int  # row in the file, counting from 1, as a spreadsheet shows it
    date: dt.date
    description: str
    amount: Decimal
    balance: Decimal | None


@dataclass(frozen=True)
class SkippedRow:
    number: int
    reason: str
    text: str


@dataclass
class Extraction:
    columns: list[str]
    header_row: int
    mapping: Mapping  # with date order and decimal separator resolved
    rows: list[StatementRow] = field(default_factory=list)
    skipped: list[SkippedRow] = field(default_factory=list)

    @property
    def newest_first(self) -> bool:
        """Banks usually list the latest movement first; trust that unless dates go up."""
        return not (self.rows and self.rows[0].date < self.rows[-1].date)

    def bank_balance(self) -> tuple[dt.date, Decimal] | None:
        """The balance the bank shows after the most recent row, if there is a balance column."""
        if not self.rows or self.mapping.balance is None:
            return None
        latest = self.rows[0] if self.newest_first else self.rows[-1]
        return None if latest.balance is None else (latest.date, latest.balance)


def column_labels(row: list[Cell]) -> list[str]:
    """Column titles, made unique and never empty."""
    labels: list[str] = []
    for index, cell in enumerate(row):
        label = cell_text(cell).strip() or f"Columna {index + 1}"
        base, copy = label, 2
        while label in labels:
            label, copy = f"{base} ({copy})", copy + 1
        labels.append(label)
    return labels


def find_header(table: Table, mapping: Mapping | None = None) -> int:
    """Index of the row with the column titles."""
    if mapping is not None:
        wanted = set(mapping.columns())
        for index, row in enumerate(table[:_HEADER_SEARCH]):
            if wanted <= set(column_labels(row)):
                return index
        names = ", ".join(f"«{name}»" for name in mapping.columns())
        raise StatementError(
            f"No encuentro las columnas {names}. ¿Es un extracto del banco de esta plantilla?"
        )
    for index, row in enumerate(table[:_HEADER_SEARCH]):
        titles = [cell for cell in row if isinstance(cell, str) and not looks_like_date(cell)]
        below = next((row for row in table[index + 1 :] if row), [])
        if len(titles) >= 2 and any(looks_like_date(cell) for cell in below):
            return index
    return next((i for i, row in enumerate(table) if sum(c is not None for c in row) >= 2), 0)


_DATE_WORDS = ("fecha contable", "fecha operacion", "f. operacion", "fecha", "date")
_DESCRIPTION_WORDS = (
    "concepto",
    "descripcion",
    "movimiento",
    "detalle",
    "comercio",
    "description",
    "concept",
)
_AMOUNT_WORDS = ("importe", "cantidad", "amount")
_DEBIT_WORDS = ("cargo", "debe", "gasto", "salida")
_CREDIT_WORDS = ("abono", "haber", "ingreso", "entrada")
_BALANCE_WORDS = ("saldo", "balance", "disponible")


def _find(labels: list[str], words: tuple[str, ...], skip: tuple[str, ...] = ()) -> str | None:
    for word in words:
        for label in labels:
            text = plain(label)
            if word in text and not any(other in text for other in skip):
                return label
    return None


def suggest_mapping(table: Table, header_row: int) -> Mapping | None:
    """A guess from the column titles; None if some required column is not obvious."""
    labels = column_labels(table[header_row])
    date = _find(labels, _DATE_WORDS, skip=("valor",)) or _find(labels, ("fecha",))
    description = _find(labels, _DESCRIPTION_WORDS, skip=("fecha",))
    amount = _find(labels, _AMOUNT_WORDS, skip=("fecha", "saldo"))
    debit = credit = None
    if amount is None:
        debit = _find(labels, _DEBIT_WORDS, skip=("fecha", "saldo"))
        credit = _find(labels, _CREDIT_WORDS, skip=("fecha", "saldo"))
    balance = _find(labels, _BALANCE_WORDS)
    if date is None or description is None or (amount is None and debit is None):
        return None
    return Mapping(
        date=date,
        description=[description],
        amount=amount,
        debit=debit,
        credit=credit,
        balance=balance,
    )


def _column(rows: list[list[Cell]], index: int) -> list[Cell]:
    return [row[index] if index < len(row) else None for row in rows]


def extract(table: Table, mapping: Mapping) -> Extraction:
    """Read every row with the mapping. Rows without a date or amount are skipped with the
    reason (totals, notes and blank lines at the end of many statements)."""
    header = find_header(table, mapping)
    labels = column_labels(table[header])
    position = {label: index for index, label in enumerate(labels)}
    missing = [name for name in mapping.columns() if name not in position]
    if missing:
        raise StatementError(f"Falta la columna «{missing[0]}» en el fichero.")
    data = table[header + 1 :]

    money_columns = [mapping.amount, mapping.debit, mapping.credit, mapping.balance]
    money_cells = [cell for name in money_columns if name for cell in _column(data, position[name])]
    resolved = mapping.model_copy(
        update={
            "date_order": mapping.date_order
            or detect_date_order(_column(data, position[mapping.date])),
            "decimal_comma": mapping.decimal_comma
            if mapping.decimal_comma is not None
            else detect_decimal_comma(money_cells),
        }
    )
    result = Extraction(columns=labels, header_row=header, mapping=resolved)
    for offset, row in enumerate(data):
        if not any(cell is not None for cell in row):
            continue
        number = header + offset + 2
        cells = {
            label: row[index] if index < len(row) else None for label, index in position.items()
        }
        text = " · ".join(cell_text(cell) for cell in row if cell is not None)
        outcome = _read_row(cells, resolved)
        if isinstance(outcome, str):
            result.skipped.append(SkippedRow(number=number, reason=outcome, text=text[:200]))
        else:
            date, description, amount, balance = outcome
            result.rows.append(
                StatementRow(
                    number=number,
                    date=date,
                    description=description,
                    amount=amount,
                    balance=balance,
                )
            )
    return result


def _read_row(
    cells: dict[str, Cell], mapping: Mapping
) -> str | tuple[dt.date, str, Decimal, Decimal | None]:
    """The row's values, or why it is skipped."""
    comma = bool(mapping.decimal_comma)
    try:
        date = parse_date(cells[mapping.date], mapping.date_order or "dmy")
    except ValueError:
        date = None
    try:
        if mapping.amount is not None:
            amount = parse_amount(cells[mapping.amount], decimal_comma=comma)
        else:
            debit = (
                parse_amount(cells[mapping.debit], decimal_comma=comma) if mapping.debit else None
            )
            credit = (
                parse_amount(cells[mapping.credit], decimal_comma=comma) if mapping.credit else None
            )
            amount = None
            if debit is not None or credit is not None:
                amount = abs(credit or Decimal(0)) - abs(debit or Decimal(0))
    except ValueError as exc:
        return str(exc) if date else "Sin fecha ni importe."
    if date is None:
        return "Sin fecha." if amount is not None else "Sin fecha ni importe."
    if amount is None:
        return "Sin importe."
    amount = round_cents(-amount if mapping.invert_sign else amount)
    if amount == 0:
        return "Importe cero."
    description = " ".join(
        cell_text(cells[name]) for name in mapping.description if cells[name] is not None
    )
    description = re.sub(r"\s+", " ", description).strip()[:MAX_DESCRIPTION]
    balance = None
    if mapping.balance is not None:
        try:
            raw = parse_amount(cells[mapping.balance], decimal_comma=comma)
            balance = None if raw is None else round_cents(raw)
        except ValueError:
            balance = None
    return date, description, amount, balance

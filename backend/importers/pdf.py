"""Bank statements in PDF (RF-IMP-03, brought forward for Bankinter).

Only digital PDFs, the ones the bank generates, and only layouts we know: each bank has its own
reader. The amounts are trusted only if the balances add up line by line, so a misread line
stops the import instead of creating a wrong movement.
"""

import datetime as dt
import io
import re
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from importers.statement import MAX_DESCRIPTION, StatementRow
from importers.table import UnreadableFileError
from importers.values import parse_amount, parse_date

MAX_PAGES = 100


class StatementMismatchError(UnreadableFileError):
    """The balances of the statement do not add up: something was misread."""


@dataclass(frozen=True)
class PdfStatement:
    reader: str  # shown to the user, e.g. "Bankinter (extracto PDF)"
    rows: list[StatementRow]  # oldest first


def read_pdf(content: bytes) -> PdfStatement:
    text = _pdf_text(content)
    for recognises, read in _READERS:
        if recognises(text):
            return read(text)
    raise UnreadableFileError(
        "Este PDF no es de un banco que sepamos leer (por ahora, extractos de Bankinter). "
        "Descarga los movimientos en Excel o CSV."
    )


def _pdf_text(content: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(content))
        # Many banks encrypt their PDFs with an empty password: they open without asking.
        if reader.is_encrypted and not reader.decrypt(""):
            raise UnreadableFileError(
                "El PDF tiene contraseña. Ábrelo, guárdalo sin contraseña y vuelve a subirlo."
            )
        if len(reader.pages) > MAX_PAGES:
            raise UnreadableFileError(f"El PDF tiene más de {MAX_PAGES} páginas.")
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except (PdfReadError, ValueError, KeyError, TypeError) as exc:
        if isinstance(exc, UnreadableFileError):
            raise
        raise UnreadableFileError("No se puede leer el PDF. ¿Está dañado?") from exc


# --- Bankinter --------------------------------------------------------------------------------

_AMOUNT = r"-?\d{1,3}(?:\.\d{3})*,\d{2}"
_BANKINTER_LINE = re.compile(
    rf"^(\d{{2}}-\d{{2}}-\d{{2}})\s+(\S+)\s+(\d{{2}}-\d{{2}}-\d{{2}})\s+(.+?)\s+({_AMOUNT})\s+({_AMOUNT})$"
)
# "**SALDO ANTERIOR EN EUROS**" opens a statement; "S A L D O  A N T E R( E U R )" opens a
# continuation page with the balance carried over.
_BANKINTER_OPENING = re.compile(rf"\*\*SALDO ANTERIOR EN EUROS\*\*\s+({_AMOUNT})$")
_BANKINTER_CARRIED = re.compile(rf"^S\s*A\s*L\s*D\s*O\s+A\s*N\s*T\s*E\s*R.*?\s+({_AMOUNT})$")
_BANKINTER_CLOSING = re.compile(rf"\*\*SALDO FINAL EN EUROS\*\*\s+({_AMOUNT})$")


def _is_bankinter(text: str) -> bool:
    return "BKBKESMM" in text or "bankinter" in text.lower()


def _money(text: str) -> Decimal:
    value = parse_amount(text)
    assert value is not None  # noqa: S101  # the pattern only matches amounts
    return value


def _read_bankinter(text: str) -> PdfStatement:
    """Each monthly statement starts from the previous balance; every line shows the amount
    without sign and the balance after it, so the sign is the change in balance."""
    statements: list[list[StatementRow]] = []
    balance: Decimal | None = None
    number = 0
    for raw in text.splitlines():
        line = " ".join(raw.split())
        if match := _BANKINTER_OPENING.search(line):
            statements.append([])
            balance = _money(match.group(1))
        elif match := _BANKINTER_CARRIED.match(line):
            carried = _money(match.group(1))
            if balance is not None and carried != balance:
                raise StatementMismatchError(_mismatch(number, balance, carried))
        elif match := _BANKINTER_CLOSING.search(line):
            closing = _money(match.group(1))
            if balance is not None and closing != balance:
                raise StatementMismatchError(_mismatch(number, balance, closing))
        elif match := _BANKINTER_LINE.match(line):
            if balance is None or not statements:
                raise StatementMismatchError(
                    "No encuentro el saldo anterior del extracto: no puedo comprobar los importes."
                )
            number += 1
            date_text, _reference, _value_date, concept, amount_text, after_text = match.groups()
            size, after = _money(amount_text), _money(after_text)
            change = after - balance
            if abs(change) != size:
                raise StatementMismatchError(
                    f"Los saldos del extracto no cuadran en el movimiento {number} («{concept}»): "
                    f"el importe es {_es(size)} pero el saldo pasa de {_es(balance)} a "
                    f"{_es(after)}. No se ha importado nada."
                )
            date = parse_date(date_text)
            assert date is not None  # noqa: S101  # the pattern only matches dates
            statements[-1].append(
                StatementRow(
                    number=number,
                    date=date,
                    description=concept[:MAX_DESCRIPTION],
                    amount=change,
                    balance=after,
                )
            )
            balance = after
    rows = _chronological([rows for rows in statements if rows])
    if not rows:
        raise UnreadableFileError("El extracto de Bankinter no tiene movimientos.")
    return PdfStatement(reader="Bankinter (extracto PDF)", rows=rows)


def _mismatch(number: int, expected: Decimal, found: Decimal) -> str:
    return (
        f"Los saldos del extracto no cuadran tras el movimiento {number}: debería ser "
        f"{_es(expected)} y pone {_es(found)}. No se ha importado nada."
    )


def _es(amount: Decimal) -> str:
    """1234.5 → "1.234,50", as the statement writes it."""
    return f"{amount:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _chronological(statements: list[list[StatementRow]]) -> list[StatementRow]:
    """A PDF may hold several months in any order: oldest statement first, and a month that
    appears twice only once."""
    seen: set[tuple[dt.date, Decimal, int]] = set()
    rows: list[StatementRow] = []
    for statement in sorted(statements, key=lambda rows: rows[0].date):
        identity = (statement[0].date, statement[0].balance or Decimal(0), len(statement))
        if identity not in seen:
            seen.add(identity)
            rows.extend(statement)
    return rows


_READERS: list[tuple[Callable[[str], bool], Callable[[str], PdfStatement]]] = [
    (_is_bankinter, _read_bankinter),
]

"""Amounts and dates as Spanish banks write them in their exports."""

import datetime as dt
import re
import unicodedata
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation
from typing import Literal

# A cell after reading the file: spreadsheets give typed values, text files give strings.
type Cell = str | Decimal | dt.date | None

type DateOrder = Literal["dmy", "ymd", "mdy"]

_NOISE = re.compile(r"\s|€|\$|£|EUR|USD|GBP", re.IGNORECASE)
# Minus sign, en dash and em dash, which some exports use for negative amounts.
_MINUS = str.maketrans(dict.fromkeys(map(chr, (0x2212, 0x2013, 0x2014)), "-"))
_COMMA_DECIMAL = re.compile(r"^(\d+|\d{1,3}(\.\d{3})+)(,\d+)?$")
_DOT_DECIMAL = re.compile(r"^(\d+|\d{1,3}(,\d{3})+)(\.\d+)?$")
_DATE = re.compile(r"^(\d{1,4})[/\-.](\d{1,2})[/\-.](\d{1,4})$")
_COMPACT_DATE = re.compile(r"^(\d{4})(\d{2})(\d{2})$")
_NAMED_DATE = re.compile(r"^(\d{1,2})[\s/\-.]+([a-z]{3,})\.?[\s/\-.]+(\d{2,4})$")
_MONTHS = {
    name: number
    for number, names in enumerate(
        (
            ("ene", "enero", "jan", "january"),
            ("feb", "febrero", "february"),
            ("mar", "marzo", "march"),
            ("abr", "abril", "apr", "april"),
            ("may", "mayo"),
            ("jun", "junio", "june"),
            ("jul", "julio", "july"),
            ("ago", "agosto", "aug", "august"),
            ("sep", "sept", "septiembre", "setiembre", "september"),
            ("oct", "octubre", "october"),
            ("nov", "noviembre", "november"),
            ("dic", "diciembre", "dec", "december"),
        ),
        start=1,
    )
    for name in names
}
# Excel stores dates as days since 30/12/1899 when the cell has no date format.
_EXCEL_EPOCH = dt.date(1899, 12, 30)


def plain(text: str) -> str:
    """Lowercase without accents, for comparing labels and concepts."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower().strip()


def cell_text(cell: Cell) -> str:
    """How a cell reads to a person."""
    if cell is None:
        return ""
    if isinstance(cell, dt.date):
        return cell.strftime("%d/%m/%Y")
    return str(cell)


def parse_amount(cell: Cell, *, decimal_comma: bool = True) -> Decimal | None:
    """An amount, or None for an empty cell. Raises ValueError if it is not a number.

    Accepts the usual ways of writing a negative amount: -12,50 · 12,50- · (12,50).
    """
    if cell is None:
        return None
    if isinstance(cell, Decimal):
        return cell
    if isinstance(cell, dt.date):
        raise ValueError("Es una fecha, no un importe.")
    text = _NOISE.sub("", cell.translate(_MINUS))
    if not text:
        return None
    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative, text = True, text[1:-1]
    if text.endswith("-"):
        negative, text = not negative, text[:-1]
    if text[:1] in "+-":
        negative, text = negative != (text[0] == "-"), text[1:]
    pattern = _COMMA_DECIMAL if decimal_comma else _DOT_DECIMAL
    if not pattern.match(text):
        raise ValueError(f"«{cell}» no es un importe.")
    text = text.replace(".", "").replace(",", ".") if decimal_comma else text.replace(",", "")
    try:
        value = Decimal(text)
    except InvalidOperation as exc:  # pragma: no cover - the pattern already checked it
        raise ValueError(f"«{cell}» no es un importe.") from exc
    return -value if negative else value


def detect_decimal_comma(cells: Iterable[Cell]) -> bool:
    """Whether a column writes decimals with a comma (1.234,56) or a dot (1,234.56).

    Spanish banks use the comma, so that wins when the column gives no clue.
    """
    comma = dot = 0
    for cell in cells:
        if isinstance(cell, str):
            text = _NOISE.sub("", cell).rstrip("-)")
            if re.search(r",\d{1,2}$", text):
                comma += 1
            elif re.search(r"\.\d{1,2}$", text):
                dot += 1
    return comma >= dot


def _build_date(year: int, month: int, day: int) -> dt.date:
    if year < 100:
        year += 2000
    return dt.date(year, month, day)


def parse_date(cell: Cell, order: DateOrder = "dmy") -> dt.date | None:
    """A date, or None for an empty cell. Raises ValueError if it is not a date."""
    if cell is None:
        return None
    if isinstance(cell, dt.datetime):
        return cell.date()
    if isinstance(cell, dt.date):
        return cell
    if isinstance(cell, Decimal):
        if cell == cell.to_integral_value() and 20_000 <= cell <= 80_000:
            return _EXCEL_EPOCH + dt.timedelta(days=int(cell))
        raise ValueError(f"«{cell}» no es una fecha.")
    text = plain(cell)
    # "15/10/2026 10:23" or "2026-10-15T10:23:00": the time does not matter.
    head = re.split(r"[ t]", text, maxsplit=1)[0]
    if _DATE.match(head) or _COMPACT_DATE.match(head):
        text = head
    if not text:
        return None
    try:
        if match := _DATE.match(text):
            a, b, c = (int(part) for part in match.groups())
            if order == "ymd" or len(match.group(1)) == 4:
                return _build_date(a, b, c)
            if order == "mdy":
                return _build_date(c, a, b)
            return _build_date(c, b, a)
        if match := _COMPACT_DATE.match(text):
            return dt.date(*(int(part) for part in match.groups()))
        if match := _NAMED_DATE.match(text):
            day, month, year = match.groups()
            if month in _MONTHS:
                return _build_date(int(year), _MONTHS[month], int(day))
    except ValueError:
        pass
    raise ValueError(f"«{cell}» no es una fecha.")


def detect_date_order(cells: Iterable[Cell]) -> DateOrder:
    """The order of day, month and year that makes sense of every date in a column."""
    texts = [cell for cell in cells if isinstance(cell, str) and cell.strip()][:500]
    for order in ("dmy", "ymd", "mdy"):
        try:
            for text in texts:
                parse_date(text, order)
        except ValueError:
            continue
        return order
    return "dmy"


def looks_like_date(cell: Cell) -> bool:
    try:
        return parse_date(cell) is not None
    except ValueError:
        return False

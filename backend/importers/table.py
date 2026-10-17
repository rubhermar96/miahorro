"""Read a statement file into rows of cells: CSV/TXT, XLSX, or the HTML tables that some banks
download with an .xls name."""

import csv
import datetime as dt
import io
from decimal import Decimal
from html.parser import HTMLParser
from typing import Any

from openpyxl import load_workbook

from importers.values import Cell

type Table = list[list[Cell]]

MAX_ROWS = 10_000
_DELIMITERS = (";", ",", "\t", "|")


class UnreadableFileError(ValueError):
    """The file cannot be read as a statement; the message is for the user."""


def read_table(content: bytes) -> Table:
    """The rows of the first sheet or table in the file, without empty rows."""
    if not content.strip():
        raise UnreadableFileError("El fichero está vacío.")
    head = content[:2048].lstrip().lower()
    if content.startswith(b"%PDF"):
        raise UnreadableFileError(
            "Los PDF no se pueden importar. Descarga los movimientos en Excel o CSV desde tu "
            "banca online."
        )
    if content.startswith(b"PK\x03\x04"):
        rows = _read_xlsx(content)
    elif content.startswith(b"\xd0\xcf\x11\xe0"):
        raise UnreadableFileError(
            "Es un Excel antiguo (.xls). Ábrelo y guárdalo como .xlsx o CSV, o descárgalo en "
            "otro formato."
        )
    elif head.startswith((b"<", b"\xef\xbb\xbf<")) and b"<table" in content[:200_000].lower():
        rows = _read_html(_decode(content))
    else:
        rows = _read_csv(_decode(content))
    # Blank rows stay, so row numbers match what a spreadsheet shows.
    table = [_trim(row) for row in rows]
    while table and not table[-1]:
        table.pop()
    if not table:
        raise UnreadableFileError("El fichero no tiene ninguna fila con datos.")
    if len(table) > MAX_ROWS:
        raise UnreadableFileError(
            f"El fichero tiene más de {MAX_ROWS} filas: impórtalo por partes."
        )
    return table


def _trim(row: list[Cell]) -> list[Cell]:
    while row and row[-1] is None:
        row = row[:-1]
    return row


def _text(value: str) -> str | None:
    cleaned = " ".join(value.replace("\xa0", " ").split())
    return cleaned or None


def _decode(content: bytes) -> str:
    """UTF-8 when it is, otherwise Windows-1252, what Spanish banks use (ñ, á, €)."""
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = content.decode("latin-1")
    if "\x00" in text:
        raise UnreadableFileError("No parece un extracto: no es un fichero de texto ni un Excel.")
    return text


def _read_csv(text: str) -> list[list[Cell]]:
    lines = [line for line in text.splitlines() if line.strip()]
    delimiter = _guess_delimiter(lines[:30])
    # Blank lines come out as empty rows, so row numbers match the file.
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)
    return [[_text(value) for value in row] for row in reader]


def _guess_delimiter(lines: list[str]) -> str:
    """The delimiter that splits the most lines into the same number of columns (2 or more)."""

    def score(delimiter: str) -> tuple[int, int]:
        counts = [len(row) for row in csv.reader(lines, delimiter=delimiter)]
        usual = max(set(counts), key=counts.count)
        return (counts.count(usual) if usual > 1 else 0, usual)

    return max(_DELIMITERS, key=score)


def _read_xlsx(content: bytes) -> list[list[Cell]]:
    try:
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:  # openpyxl raises many kinds of errors for broken files
        raise UnreadableFileError("No se puede abrir el Excel. ¿Está dañado o protegido?") from exc
    try:
        sheet = workbook.worksheets[0]
        rows: list[list[Cell]] = []
        for values in sheet.iter_rows(values_only=True):
            rows.append([_xlsx_cell(value) for value in values])
            if len(rows) > MAX_ROWS * 2:
                break
        return rows
    finally:
        workbook.close()


def _xlsx_cell(value: Any) -> Cell:
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        # Excel keeps numbers as binary floats: the shortest text that reads back the same
        # value is what the cell shows (12.34, not 12.339999...).
        return Decimal(repr(value))
    return _text(str(value))


class _TableParser(HTMLParser):
    """The rows of the first <table> with data."""

    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[Cell]]] = []
        self._row: list[Cell] | None = None
        self._cell: list[str] | None = None
        self._depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._depth += 1
            if self._depth == 1:
                self.tables.append([])
        elif tag == "tr" and self._depth:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
        elif tag == "br" and self._cell is not None:
            self._cell.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._row is not None and self._cell is not None:
            self._row.append(_text("".join(self._cell)))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self.tables:
                self.tables[-1].append(self._row)
            self._row = None
        elif tag == "table" and self._depth:
            self._depth -= 1

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


def _read_html(text: str) -> list[list[Cell]]:
    parser = _TableParser()
    parser.feed(text)
    parser.close()
    # The movements are the biggest table; the others are headers and logos.
    return max(parser.tables, key=len, default=[])

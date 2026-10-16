import datetime as dt
from decimal import Decimal

import pytest

from importers.statement import Mapping, StatementError, extract, find_header, suggest_mapping
from importers.table import UnreadableFileError, read_table
from tests.importers.samples import (
    DEBIT_CREDIT_CSV,
    HTML_XLS,
    SEMICOLON_CSV,
    xlsx_statement,
)


def rows_of(content: bytes) -> list[tuple[int, dt.date, str, str, str | None]]:
    table = read_table(content)
    mapping = suggest_mapping(table, find_header(table))
    assert mapping is not None
    return [
        (
            row.number,
            row.date,
            row.description,
            str(row.amount),
            None if row.balance is None else str(row.balance),
        )
        for row in extract(table, mapping).rows
    ]


def test_semicolon_csv_with_preamble_and_totals() -> None:
    table = read_table(SEMICOLON_CSV)
    header = find_header(table)
    mapping = suggest_mapping(table, header)

    assert header == 3
    assert mapping == Mapping(
        date="Fecha operación", description=["Concepto"], amount="Importe", balance="Saldo"
    )
    extraction = extract(table, mapping)
    assert [(r.date, r.description, r.amount, r.balance) for r in extraction.rows] == [
        (
            dt.date(2026, 10, 15),
            "COMPRA TARJ. 1234 MERCADONA VALENCIA",
            Decimal("-45.20"),
            Decimal("1954.80"),
        ),
        (dt.date(2026, 10, 14), "NÓMINA OCTUBRE", Decimal("2000.00"), Decimal("2000.00")),
    ]
    assert [(s.number, s.reason) for s in extraction.skipped] == [(7, "Sin fecha.")]
    assert extraction.newest_first
    assert extraction.bank_balance() == (dt.date(2026, 10, 15), Decimal("1954.80"))


def test_debit_and_credit_columns() -> None:
    assert rows_of(DEBIT_CREDIT_CSV) == [
        (2, dt.date(2026, 10, 1), "Recibo luz", "-60.10", "939.90"),
        (3, dt.date(2026, 10, 2), "Bizum de Luis", "15.00", "954.90"),
    ]


def test_xlsx_with_typed_cells() -> None:
    assert rows_of(xlsx_statement()) == [
        (4, dt.date(2026, 10, 5), "GASOLINERA REPSOL", "-50.10", "949.90"),
        (5, dt.date(2026, 10, 6), "TRANSFERENCIA RECIBIDA", "1234.56", "2184.46"),
    ]


def test_html_table_saved_as_xls() -> None:
    assert rows_of(HTML_XLS) == [
        (2, dt.date(2026, 10, 3), "AMAZON EU", "-19.99", None),
        (3, dt.date(2026, 10, 4), "DEVOLUCION", "5.00", None),
    ]


def test_a_template_finds_its_columns_whatever_comes_before() -> None:
    mapping = Mapping(date="Fecha valor", description=["Concepto"], amount="Importe")
    table = read_table(b"Otro preambulo\nMas texto\n" + SEMICOLON_CSV)

    extraction = extract(table, mapping)

    assert extraction.header_row == 5
    assert len(extraction.rows) == 2


def test_a_template_for_another_bank_says_so() -> None:
    table = read_table(DEBIT_CREDIT_CSV)
    mapping = Mapping(date="Fecha operación", description=["Concepto"], amount="Importe")

    with pytest.raises(StatementError, match="«Fecha operación», «Concepto», «Importe»"):
        extract(table, mapping)


def test_cards_that_show_expenses_as_positive() -> None:
    table = read_table(b"Fecha;Comercio;Importe\n01/10/2026;CINE;9,50\n02/10/2026;ABONO;-9,50\n")
    mapping = Mapping(date="Fecha", description=["Comercio"], amount="Importe", invert_sign=True)

    assert [row.amount for row in extract(table, mapping).rows] == [
        Decimal("-9.50"),
        Decimal("9.50"),
    ]


def test_several_description_columns_are_joined() -> None:
    table = read_table(b"Fecha;Concepto;Mas datos;Importe\n01/10/2026;RECIBO;IBERDROLA;-60\n")
    mapping = Mapping(date="Fecha", description=["Concepto", "Mas datos"], amount="Importe")

    assert extract(table, mapping).rows[0].description == "RECIBO IBERDROLA"


def test_bad_rows_are_skipped_with_the_reason() -> None:
    table = read_table(
        b"Fecha;Concepto;Importe\n"
        b"01/10/2026;OK;-1\n"
        b"02/10/2026;MAL;doce\n"
        b"03/10/2026;CERO;0,00\n"
        b"ayer;SIN FECHA;-3\n"
    )
    mapping = Mapping(date="Fecha", description=["Concepto"], amount="Importe")

    extraction = extract(table, mapping)

    assert [row.description for row in extraction.rows] == ["OK"]
    assert [(s.number, s.reason) for s in extraction.skipped] == [
        (3, "«doce» no es un importe."),
        (4, "Importe cero."),
        (5, "Sin fecha."),
    ]


def test_same_column_titles_are_told_apart() -> None:
    table = read_table(b"Fecha;Fecha;Concepto;;Importe\n01/10/2026;02/10/2026;X;;-1\n")
    mapping = Mapping(date="Fecha (2)", description=["Concepto"], amount="Importe")

    extraction = extract(table, mapping)

    assert extraction.columns == ["Fecha", "Fecha (2)", "Concepto", "Columna 4", "Importe"]
    assert extraction.rows[0].date == dt.date(2026, 10, 2)


def test_nothing_obvious_to_suggest() -> None:
    table = read_table(b"A;B;C\n01/10/2026;x;1\n")

    assert suggest_mapping(table, find_header(table)) is None


def test_mapping_needs_amounts() -> None:
    with pytest.raises(ValueError, match="columna del importe"):
        Mapping(date="Fecha", description=["Concepto"])
    with pytest.raises(ValueError, match="no ambas"):
        Mapping(date="Fecha", description=["Concepto"], amount="Importe", debit="Cargo")


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"", "vacío"),
        (b"%PDF-1.7 ...", "PDF"),
        (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1rest", "Excel antiguo"),
        (b"PK\x03\x04broken zip", "No se puede abrir el Excel"),
        (b"\x00\x01\x02\x03binary", "no es un fichero de texto"),
    ],
)
def test_unreadable_files(content: bytes, message: str) -> None:
    with pytest.raises(UnreadableFileError, match=message):
        read_table(content)


def test_too_many_rows() -> None:
    content = b"Fecha;Concepto;Importe\n" + b"01/10/2026;X;-1\n" * 10_001
    with pytest.raises(UnreadableFileError, match="por partes"):
        read_table(content)

import datetime as dt
from decimal import Decimal

import pytest

from importers.pdf import StatementMismatchError, read_pdf
from importers.table import UnreadableFileError
from tests.importers.pdf_samples import bankinter_pdf, make_pdf


def test_bankinter_statement_signs_come_from_the_balance() -> None:
    statement = read_pdf(bankinter_pdf())

    assert statement.reader == "Bankinter (extracto PDF)"
    assert [(r.date, r.description, r.amount, r.balance) for r in statement.rows] == [
        (dt.date(2026, 8, 4), "RECIBO /COMUNIDAD EJEMPLO", Decimal("-12.24"), Decimal("1187.76")),
        (dt.date(2026, 8, 31), "RECIBO VISA CLASICA", Decimal("-187.76"), Decimal("1000.00")),
        (
            dt.date(2026, 9, 1),
            "TRANSF NOMI /EMPRESA EJEMPLO SL",
            Decimal("1500.00"),
            Decimal("2500.00"),
        ),
        (dt.date(2026, 9, 3), "CAJERO BANCO OF.0001", Decimal("-100.00"), Decimal("2400.00")),
        (
            dt.date(2026, 9, 5),
            "PAGO BIZUM DE Persona Ejemplo",
            Decimal("25.50"),
            Decimal("2425.50"),
        ),
        (dt.date(2026, 9, 30), "RECIBO VISA CLASICA", Decimal("-425.50"), Decimal("2000.00")),
    ]  # oldest month first, although the PDF starts with September


def test_a_balance_that_does_not_add_up_stops_everything() -> None:
    with pytest.raises(StatementMismatchError, match=r"el saldo pasa de 2.425,50 a 2.100,00"):
        read_pdf(bankinter_pdf(broken=True))


def test_a_month_repeated_in_the_file_counts_once() -> None:
    pages = [
        [
            "**SALDO ANTERIOR EN EUROS** 10,00",
            "01-09-26 1 01-09-26 CAFE 1,50 8,50",
            "**SALDO FINAL EN EUROS** 8,50",
            "BKBKESMM",
        ]
    ]

    assert len(read_pdf(make_pdf(pages * 2)).rows) == 1


def test_lines_before_the_opening_balance_cannot_be_checked() -> None:
    pdf = make_pdf([["BKBKESMM", "01-09-26 1 01-09-26 CAFE 1,50 8,50"]])

    with pytest.raises(StatementMismatchError, match="saldo anterior"):
        read_pdf(pdf)


def test_unknown_banks_and_broken_pdfs() -> None:
    with pytest.raises(UnreadableFileError, match="no es de un banco que sepamos leer"):
        read_pdf(make_pdf([["Extracto de otro banco", "01-09-26 CAFE -1,50"]]))
    with pytest.raises(UnreadableFileError, match="No se puede leer el PDF"):
        read_pdf(b"%PDF-1.4 not really")

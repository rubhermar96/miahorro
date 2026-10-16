"""Made-up statements in the shapes Spanish banks export."""

import datetime as dt
import io

from openpyxl import Workbook

# Preamble rows, ";" separator, comma decimals, Windows-1252, a totals row at the end.
SEMICOLON_CSV = (
    "Movimientos de la cuenta;ES12 **** 1234\r\n"
    "Titular;ANA GARCÍA\r\n"
    "\r\n"
    "Fecha operación;Fecha valor;Concepto;Importe;Saldo\r\n"
    "15/10/2026;15/10/2026;COMPRA TARJ. 1234 MERCADONA VALENCIA;-45,20;1.954,80\r\n"
    "14/10/2026;14/10/2026;NÓMINA OCTUBRE;2.000,00;2.000,00\r\n"
    "Total;;;1.954,80;\r\n"
).encode("cp1252")

# Separate columns for money out and in, "," separator with quoted comma decimals, UTF-8 BOM.
DEBIT_CREDIT_CSV = (
    "﻿"
    '"Fecha","Descripción","Cargo","Abono","Saldo"\n'
    '"01/10/2026","Recibo luz","60,10","","939,90"\n'
    '"02/10/2026","Bizum de Luis","","15,00","954,90"\n'
).encode()

HTML_XLS = b"""<html><body>
<table><tr><td>Banco Ejemplo</td></tr></table>
<table>
<tr><th>Fecha</th><th>Concepto</th><th>Importe</th></tr>
<tr><td>03/10/2026</td><td>AMAZON&nbsp;EU</td><td>-19,99</td></tr>
<tr><td>04/10/2026</td><td>DEVOLUCION</td><td>5,00</td></tr>
</table></body></html>"""


def xlsx_statement() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(["Extracto de movimientos"])
    sheet.append([])
    sheet.append(["F. Operación", "Descripción", "Importe (EUR)", "Saldo"])
    sheet.append([dt.datetime(2026, 10, 5), "GASOLINERA REPSOL", -50.1, 949.9])  # noqa: DTZ001
    sheet.append([dt.datetime(2026, 10, 6), "TRANSFERENCIA RECIBIDA", 1234.56, 2184.46])  # noqa: DTZ001
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()

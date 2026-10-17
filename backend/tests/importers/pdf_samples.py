"""Made-up PDF statements with the text layout of real ones (no real data)."""


def make_pdf(pages: list[list[str]]) -> bytes:
    """A minimal PDF with one line of text per entry, top to bottom, on each page."""
    objects: list[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    font = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    pages_id = len(objects) + 1 + 2 * len(pages)  # reserved after the pages and their contents
    page_ids = []
    for lines in pages:
        commands = ["BT /F1 9 Tf 11 TL 40 800 Td"]
        for line in lines:
            escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            commands.append(f"({escaped}) Tj T*")
        commands.append("ET")
        stream = "\n".join(commands).encode("cp1252")
        content = add(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        page_ids.append(
            add(
                b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 595 842] "
                b"/Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>"
                % (pages_id, font, content)
            )
        )
    kids = b" ".join(b"%d 0 R" % page for page in page_ids)
    assert add(b"<< /Type /Pages /Kids [%s] /Count %d >>" % (kids, len(page_ids))) == pages_id
    catalog = add(b"<< /Type /Catalog /Pages %d 0 R >>" % pages_id)

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        catalog,
        xref,
    )
    return bytes(out)


_HEADER = [
    "Movimientos y saldo de su cuenta",
    "Fecha Oficina Moneda Hoja",
    "30-09-26 0001 - OFICINA DE PRUEBA EUR 1",
    "Titulares",
    "ANA EJEMPLO EJEMPLO",
    "Fecha Referencia Fecha valor Descripción Cargos(-) Abonos(+) Saldo",
]
_FOOTER = ["Nº IBAN BIC", "ES00 0000 0000 0000 0000 0000 BKBKESMM"]


def bankinter_pdf(*, broken: bool = False) -> bytes:
    """Two monthly statements, newest first as the bank puts them; September runs onto a
    second page. With broken, one balance does not follow from the amounts."""
    september = [
        *_HEADER,
        "**SALDO ANTERIOR EN EUROS** 1.000,00",
        "01-09-26 11 01-09-26 TRANSF NOMI /EMPRESA EJEMPLO SL 1.500,00 2.500,00",
        "03-09-26 12 02-09-26 CAJERO BANCO OF.0001 100,00 2.400,00",
        "05-09-26 13 05-09-26 PAGO BIZUM DE Persona Ejemplo 25,50 2.425,50",
        *_FOOTER,
    ]
    september_2 = [
        *_HEADER,
        "S A L D O  A N T E R( E U R ) 2.425,50",
        "30-09-26 14 30-09-26 RECIBO VISA CLASICA 425,50 " + ("2.100,00" if broken else "2.000,00"),
        "**SALDO FINAL EN EUROS** " + ("2.100,00" if broken else "2.000,00"),
        *_FOOTER,
    ]
    august = [
        *_HEADER,
        "**SALDO ANTERIOR EN EUROS** 1.200,00",
        "04-08-26 21 04-08-26 RECIBO /COMUNIDAD EJEMPLO 12,24 1.187,76",
        "31-08-26 22 31-08-26 RECIBO VISA CLASICA 187,76 1.000,00",
        "**SALDO FINAL EN EUROS** 1.000,00",
        *_FOOTER,
    ]
    return make_pdf([september, september_2, august])

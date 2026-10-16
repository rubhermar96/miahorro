"""Import bank statements from CSV/XLSX files, with shared templates (RF-IMP-01, RF-IMP-07).

The file is sent twice: first to preview what would be imported (nothing is stored), then to
import the rows the user chose. Nothing of the file is kept apart from the movements.
"""

import datetime as dt
import json
import uuid
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app import ledger
from app.auth.deps import CurrentUser, DbSession
from app.importing import ClassifiedRow, classify, save_import
from app.models.accounts import Account
from app.models.imports import ImportBatch, ImportTemplate
from app.models.transactions import Transaction
from app.models.user import User
from app.ownership import get_owned_or_404, owned
from app.routers.money_types import Money
from app.routers.transactions import usable_account
from app.rules import load_rulebook
from importers.pdf import PdfStatement, read_pdf
from importers.statement import (
    Extraction,
    Mapping,
    StatementError,
    column_labels,
    extract,
    find_header,
    suggest_mapping,
)
from importers.table import Table, UnreadableFileError, read_table
from importers.values import cell_text

router = APIRouter(prefix="/api", tags=["imports"])

MAX_FILE_BYTES = 5 * 1024 * 1024
_SAMPLE_ROWS = 6


# --- Templates --------------------------------------------------------------------------------


class TemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    mapping: Mapping


class TemplateOut(TemplateIn):
    id: uuid.UUID
    mine: bool = Field(description="Created by the current user (who may delete it)")

    @classmethod
    def from_model(cls, template: ImportTemplate, user: User) -> TemplateOut:
        return cls(
            id=template.id,
            name=template.name,
            mapping=Mapping.model_validate(template.mapping),
            mine=template.created_by == user.id,
        )


@router.get("/import-templates")
def list_templates(user: CurrentUser, db: DbSession) -> list[TemplateOut]:
    """Templates shared by everyone, by name."""
    templates = db.scalars(select(ImportTemplate).order_by(func.lower(ImportTemplate.name)))
    return [TemplateOut.from_model(template, user) for template in templates]


@router.post("/import-templates", status_code=status.HTTP_201_CREATED)
def create_template(body: TemplateIn, user: CurrentUser, db: DbSession) -> TemplateOut:
    template = _new_template(db, user, body.name, body.mapping)
    db.commit()
    return TemplateOut.from_model(template, user)


def _new_template(db: DbSession, user: User, name: str, mapping: Mapping) -> ImportTemplate:
    name = name.strip()
    taken = db.scalar(
        select(ImportTemplate.id).where(func.lower(ImportTemplate.name) == name.lower())
    )
    if taken is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Ya hay una plantilla llamada «{name}». Elige otro nombre."
        )
    template = ImportTemplate(
        name=name, mapping=mapping.model_dump(mode="json"), created_by=user.id
    )
    db.add(template)
    try:
        db.flush()
    except IntegrityError as exc:  # someone else took the name at the same time
        raise HTTPException(status.HTTP_409_CONFLICT, "Ese nombre ya está en uso.") from exc
    return template


@router.delete("/import-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(template_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Response:
    """Only whoever created a template, or an administrator, can delete it."""
    template = db.get(ImportTemplate, template_id)
    if template is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if template.created_by != user.id and not user.is_admin:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Solo quien creó la plantilla puede borrarla."
        )
    db.delete(template)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Preview ----------------------------------------------------------------------------------

RowStatus = Literal["new", "duplicate", "possible_duplicate"]


class PreviewRow(BaseModel):
    number: int = Field(description="Row in the file, as a spreadsheet numbers it")
    date: dt.date
    description: str
    amount: Money
    balance: Money | None
    status: RowStatus
    category_id: uuid.UUID | None = Field(description="Category the rules give it")
    match_id: uuid.UUID | None = Field(description="Movement it may repeat (possible_duplicate)")


class SkippedRowOut(BaseModel):
    number: int
    reason: str
    text: str


class ImportPreview(BaseModel):
    columns: list[str] = Field(description="Column titles found in the file")
    sample: list[list[str]] = Field(description="First rows after the titles, as text")
    mapping: Mapping | None = Field(description="Mapping used, or suggested; null if unclear")
    template_id: uuid.UUID | None = Field(description="Template whose columns the file has")
    reader: str | None = Field(description="Bank reader used for a PDF statement")
    error: str | None = Field(description="Why the rows could not be read with the mapping")
    rows: list[PreviewRow]
    skipped: list[SkippedRowOut]
    bank_balance: Money | None = Field(description="Balance the bank shows after the last row")
    bank_balance_date: dt.date | None
    balance_then: Money | None = Field(
        description="Balance in MiAhorro on that date, after importing the new rows"
    )


async def _read_upload(file: UploadFile) -> Table | PdfStatement:
    """A table (CSV, XLSX) or, for a PDF, the statement already read by its bank's reader."""
    content = await file.read(MAX_FILE_BYTES + 1)
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE, "El fichero es demasiado grande (máximo 5 MB)."
        )
    try:
        return read_pdf(content) if content.startswith(b"%PDF") else read_table(content)
    except UnreadableFileError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc


def _parse_mapping(raw: str | None) -> Mapping | None:
    if not raw:
        return None
    try:
        return Mapping.model_validate_json(raw)
    except ValidationError as exc:
        message = next(
            (str(e["msg"]).removeprefix("Value error, ") for e in exc.errors()),
            "La configuración de columnas no es válida.",
        )
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, message) from exc


def _template_for(
    db: DbSession, table: Table, template_id: uuid.UUID | None
) -> ImportTemplate | None:
    """The chosen template, or the first one whose columns the file has."""
    if template_id is not None:
        template = db.get(ImportTemplate, template_id)
        if template is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "La plantilla ya no existe.")
        return template
    for template in db.scalars(select(ImportTemplate).order_by(ImportTemplate.created_at)):
        try:
            find_header(table, Mapping.model_validate(template.mapping))
        except StatementError, ValidationError:
            continue
        return template
    return None


def _balance_then(
    db: DbSession, account: Account, on: dt.date, rows: list[ClassifiedRow]
) -> Decimal:
    new = [(item.row.date, item.row.amount) for item in rows if item.status == "new"]
    return ledger.balance_on(db, account, on, extra=new)


@router.post("/imports/preview")
async def preview_import(
    user: CurrentUser,
    db: DbSession,
    file: Annotated[UploadFile, File(description="CSV, TXT or XLSX statement")],
    account_id: Annotated[uuid.UUID, Form()],
    mapping: Annotated[str | None, Form(description="Mapping as JSON; omit to detect")] = None,
    template_id: Annotated[uuid.UUID | None, Form()] = None,
) -> ImportPreview:
    """What the file would add to the account. Stores nothing."""
    account = get_owned_or_404(db, Account, account_id, user)
    table = await _read_upload(file)
    if isinstance(table, PdfStatement):
        preview = _empty_preview(columns=[], sample=[], mapping=None, template_id=None, error=None)
        preview.reader = table.reader
        extraction = Extraction(columns=[], header_row=0, mapping=None, rows=table.rows)
        return _fill(preview, extraction, db, account, user)
    chosen = _parse_mapping(mapping)
    template = None
    if chosen is None:
        template = _template_for(db, table, template_id)
        chosen = Mapping.model_validate(template.mapping) if template else None
    try:
        header = find_header(table, chosen)
    except StatementError:
        header = find_header(table)  # show the file's own columns so the user can map them
    if chosen is None:
        chosen = suggest_mapping(table, header)

    preview = _empty_preview(
        columns=column_labels(table[header]),
        sample=[[cell_text(cell) for cell in row] for row in table[header + 1 :] if row][
            :_SAMPLE_ROWS
        ],
        mapping=chosen,
        template_id=template.id if template else None,
        error=None if chosen else "Indica qué columna es la fecha, el concepto y el importe.",
    )
    if chosen is None:
        return preview
    try:
        extraction = extract(table, chosen)
    except StatementError as exc:
        preview.error = str(exc)
        return preview
    preview.mapping = extraction.mapping
    return _fill(preview, extraction, db, account, user)


def _empty_preview(
    *,
    columns: list[str],
    sample: list[list[str]],
    mapping: Mapping | None,
    template_id: uuid.UUID | None,
    error: str | None,
) -> ImportPreview:
    return ImportPreview(
        columns=columns,
        sample=sample,
        mapping=mapping,
        template_id=template_id,
        reader=None,
        error=error,
        rows=[],
        skipped=[],
        bank_balance=None,
        bank_balance_date=None,
        balance_then=None,
    )


def _fill(
    preview: ImportPreview, extraction: Extraction, db: DbSession, account: Account, user: User
) -> ImportPreview:
    """The rows with their status and category, and the balance check."""
    classified = classify(db, account, extraction.rows, load_rulebook(db, user))
    preview.rows = [
        PreviewRow(
            number=item.row.number,
            date=item.row.date,
            description=item.row.description,
            amount=item.row.amount,
            balance=item.row.balance,
            status=item.status,
            category_id=item.category_id,
            match_id=item.match_id,
        )
        for item in classified
    ]
    preview.skipped = [
        SkippedRowOut(number=row.number, reason=row.reason, text=row.text)
        for row in extraction.skipped
    ]
    if not extraction.rows:
        preview.error = "No hay ningún movimiento que se pueda leer con estas columnas."
    if bank := extraction.bank_balance():
        preview.bank_balance_date, preview.bank_balance = bank
        preview.balance_then = _balance_then(db, account, bank[0], classified)
    return preview


# --- Import and undo --------------------------------------------------------------------------


class ImportOut(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    filename: str
    template_name: str | None
    imported: int
    skipped: int
    date_from: dt.date | None
    date_to: dt.date | None
    created_at: dt.datetime

    @classmethod
    def from_model(cls, batch: ImportBatch) -> ImportOut:
        return cls(
            id=batch.id,
            account_id=batch.account_id,
            filename=batch.filename,
            template_name=batch.template_name,
            imported=batch.imported,
            skipped=batch.skipped,
            date_from=batch.date_from,
            date_to=batch.date_to,
            created_at=batch.created_at,
        )


def _row_numbers(raw: str) -> set[int]:
    try:
        numbers = json.loads(raw)
    except json.JSONDecodeError:
        numbers = None
    if not isinstance(numbers, list) or not all(type(n) is int for n in numbers):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Indica qué filas importar (lista de números)."
        )
    return set(numbers)


@router.post("/imports", status_code=status.HTTP_201_CREATED)
async def create_import(
    user: CurrentUser,
    db: DbSession,
    file: Annotated[UploadFile, File()],
    account_id: Annotated[uuid.UUID, Form()],
    rows: Annotated[str, Form(description="JSON list of the row numbers to import")],
    mapping: Annotated[
        str | None, Form(description="Mapping as JSON, as the preview returned it (not for PDF)")
    ] = None,
    template_id: Annotated[uuid.UUID | None, Form()] = None,
    save_template_as: Annotated[
        str | None, Form(max_length=60, description="Also save the mapping as a template")
    ] = None,
) -> ImportOut:
    account = usable_account(db, account_id, user)
    table = await _read_upload(file)
    wanted = _row_numbers(rows)
    chosen = None
    if isinstance(table, PdfStatement):
        extraction = Extraction(columns=[], header_row=0, mapping=None, rows=table.rows)
    else:
        chosen = _parse_mapping(mapping)
        if chosen is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "Indica qué columna es la fecha, el concepto y el importe.",
            )
        try:
            extraction = extract(table, chosen)
        except StatementError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    classified = classify(db, account, extraction.rows, load_rulebook(db, user))
    selected = [item for item in classified if item.row.number in wanted]
    if not selected:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "No has elegido ningún movimiento."
        )

    template_name = table.reader if isinstance(table, PdfStatement) else None
    if chosen is not None and save_template_as and save_template_as.strip():
        template_name = _new_template(db, user, save_template_as, chosen).name
    elif template_id is not None and (template := db.get(ImportTemplate, template_id)):
        template_name = template.name
    batch = save_import(
        db,
        user,
        account,
        selected,
        filename=file.filename or "extracto",
        template_name=template_name,
        skipped=len(classified) - len(selected),
        newest_first=extraction.newest_first,
    )
    db.commit()
    return ImportOut.from_model(batch)


@router.get("/imports")
def list_imports(
    user: CurrentUser, db: DbSession, account_id: uuid.UUID | None = None
) -> list[ImportOut]:
    query = owned(ImportBatch, user).order_by(ImportBatch.created_at.desc())
    if account_id is not None:
        query = query.where(ImportBatch.account_id == account_id)
    return [ImportOut.from_model(batch) for batch in db.scalars(query)]


@router.delete("/imports/{import_id}", status_code=status.HTTP_204_NO_CONTENT)
def undo_import(import_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Response:
    """Delete every movement the import created, even those edited since."""
    batch = get_owned_or_404(db, ImportBatch, import_id, user)
    db.execute(
        delete(Transaction).where(Transaction.import_id == batch.id, Transaction.user_id == user.id)
    )
    db.delete(batch)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

"""Loans and mortgages (RF-PRE-01, 02, 03, 05, 07, 09) and the reference index table."""

import datetime as dt
import uuid
from decimal import Decimal
from typing import Literal, Self

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select

from app import clock, loans
from app.auth.deps import CurrentUser, DbSession
from app.models.accounts import Account
from app.models.loans import Loan, LoanPrepayment, ReferenceRate
from app.models.user import User
from app.ownership import get_owned_or_404, owned
from app.routers.money_types import Money, Rate
from finance.loans import Installment

router = APIRouter(prefix="/api", tags=["loans"])

LoanKind = Literal["mortgage", "personal", "car", "consumer", "credit_line", "p2p_owe", "p2p_lent"]
RateType = Literal["fixed", "variable", "mixed"]
System = Literal["french", "linear"]
Index = Literal["euribor_12m"]
Mode = Literal["reduce_payment", "reduce_term"]


class LoanFields(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    kind: LoanKind = "personal"
    lender: str | None = Field(default=None, max_length=60, description="Bank or person")
    principal: Money
    signed_on: dt.date
    first_payment: dt.date
    term_months: int = Field(ge=1, le=600)
    system: System = "french"
    grace_months: int = Field(default=0, ge=0)
    rate_type: RateType = "fixed"
    fixed_rate: Rate = Field(description="TIN; for variable or mixed, the initial rate")
    fixed_months: int = Field(default=0, ge=0, description="Months at the initial rate")
    index: Index | None = None
    spread: Rate | None = Field(default=None, description="Diferencial over the index")
    review_months: Literal[6, 12] = 12
    tae: Rate | None = None
    opening_fee: Money | None = None
    early_repayment_fee: Rate = Field(default=Decimal(0), description="Percent in the contract")
    account_id: uuid.UUID | None = Field(default=None, description="Account it is paid from")
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def _tidy(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Ponle un nombre al préstamo.")
        return value

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.principal <= 0:
            raise ValueError("El capital debe ser mayor que cero.")
        if self.first_payment < self.signed_on:
            raise ValueError("La primera cuota no puede ser anterior a la firma.")
        if self.grace_months >= self.term_months:
            raise ValueError("La carencia debe ser menor que el plazo.")
        if self.fixed_rate < 0 or (self.spread is not None and self.spread < -5):
            raise ValueError("Revisa el tipo de interés.")
        if self.rate_type != "fixed":
            if self.index is None or self.spread is None:
                raise ValueError(
                    "En un préstamo variable o mixto indica el índice y el diferencial."
                )
            if self.fixed_months >= self.term_months:
                raise ValueError("El periodo a tipo fijo debe ser menor que el plazo.")
        return self


class LoanUpdate(BaseModel):
    """Any of the fields; `archived` hides a finished loan."""

    name: str | None = None
    kind: LoanKind | None = None
    lender: str | None = None
    principal: Money | None = None
    signed_on: dt.date | None = None
    first_payment: dt.date | None = None
    term_months: int | None = Field(default=None, ge=1, le=600)
    system: System | None = None
    grace_months: int | None = Field(default=None, ge=0)
    rate_type: RateType | None = None
    fixed_rate: Rate | None = None
    fixed_months: int | None = Field(default=None, ge=0)
    index: Index | None = None
    spread: Rate | None = None
    review_months: Literal[6, 12] | None = None
    tae: Rate | None = None
    opening_fee: Money | None = None
    early_repayment_fee: Rate | None = None
    account_id: uuid.UUID | None = None
    note: str | None = None
    archived: bool | None = None


class NextPayment(BaseModel):
    date: dt.date
    amount: Money


class LoanOut(LoanFields):
    id: uuid.UUID
    archived: bool
    direction: Literal["owe", "owed"] = Field(description="owed: someone owes the user")
    outstanding: Money = Field(description="Capital left today")
    principal_paid: Money
    interest_paid: Money
    interest_left: Money
    next_payment: NextPayment | None
    end_date: dt.date | None
    payments_left: int
    current_rate: Rate
    warnings: list[str] = Field(description="E.g. a review without its index value")


class InstallmentOut(BaseModel):
    number: int
    date: dt.date
    rate: Rate
    payment: Money
    interest: Money
    principal: Money
    outstanding: Money
    paid: bool = Field(description="Its date has passed")
    review: bool = Field(description="The rate changes from this instalment")


class SimulationIn(BaseModel):
    date: dt.date
    amount: Money
    mode: Mode = "reduce_term"

    @model_validator(mode="after")
    def _positive(self) -> Self:
        if self.amount <= 0:
            raise ValueError("El importe debe ser mayor que cero.")
        return self


class SimulationOut(BaseModel):
    fee: Money
    fee_percent: Rate
    legal_cap: Rate | None = Field(description="Maximum the law allows; null if none")
    interest_saved: Money
    payment_before: Money | None
    payment_after: Money | None
    end_before: dt.date | None
    end_after: dt.date | None
    payments_saved: int


class PrepaymentOut(BaseModel):
    id: uuid.UUID
    date: dt.date
    amount: Money
    mode: Mode
    fee: Money


class ReferenceRateIn(BaseModel):
    index: Index = "euribor_12m"
    month: dt.date = Field(description="Any day of the month")
    value: Rate


class ReferenceRateOut(BaseModel):
    id: uuid.UUID
    index: Index
    month: dt.date
    value: Rate


def _fields(loan: Loan) -> dict[str, object]:
    return {name: getattr(loan, name) for name in LoanFields.model_fields}


def _out(db: DbSession, loan: Loan) -> LoanOut:
    today = clock.today()
    rows, rates = loans.table(db, loan, today)
    summary = loans.summarize(loan, rows, loans.prepayments_of(db, loan), today)
    return LoanOut.model_validate(
        {
            **_fields(loan),
            "id": loan.id,
            "archived": loan.archived_at is not None,
            "direction": "owed" if loan.kind == "p2p_lent" else "owe",
            "outstanding": summary.outstanding,
            "principal_paid": summary.principal_paid,
            "interest_paid": summary.interest_paid,
            "interest_left": summary.interest_left,
            "next_payment": (
                {"date": summary.next_payment.date, "amount": summary.next_payment.payment}
                if summary.next_payment
                else None
            ),
            "end_date": summary.end_date,
            "payments_left": summary.payments_left,
            "current_rate": summary.current_rate,
            "warnings": rates.warnings,
        }
    )


def _check_account(db: DbSession, user: User, account_id: uuid.UUID | None) -> None:
    if account_id is not None:
        get_owned_or_404(db, Account, account_id, user)


@router.get("/loans")
def list_loans(user: CurrentUser, db: DbSession, include_archived: bool = False) -> list[LoanOut]:
    query = owned(Loan, user).order_by(Loan.signed_on)
    if not include_archived:
        query = query.where(Loan.archived_at.is_(None))
    return [_out(db, loan) for loan in db.scalars(query)]


@router.post("/loans", status_code=status.HTTP_201_CREATED)
def create_loan(body: LoanFields, user: CurrentUser, db: DbSession) -> LoanOut:
    _check_account(db, user, body.account_id)
    loan = Loan(user_id=user.id, created_at=clock.now(), **body.model_dump())
    if loan.rate_type == "fixed":
        loan.index, loan.spread, loan.fixed_months = None, None, 0
    db.add(loan)
    db.commit()
    return _out(db, loan)


@router.get("/loans/{loan_id}")
def read_loan(loan_id: uuid.UUID, user: CurrentUser, db: DbSession) -> LoanOut:
    return _out(db, get_owned_or_404(db, Loan, loan_id, user))


@router.patch("/loans/{loan_id}")
def update_loan(loan_id: uuid.UUID, body: LoanUpdate, user: CurrentUser, db: DbSession) -> LoanOut:
    loan = get_owned_or_404(db, Loan, loan_id, user)
    changes = body.model_dump(exclude_unset=True)
    archived = changes.pop("archived", None)
    merged = LoanFields.model_validate({**_fields(loan), **changes})
    _check_account(db, user, merged.account_id)
    for name, value in merged.model_dump().items():
        setattr(loan, name, value)
    if loan.rate_type == "fixed":
        loan.index, loan.spread, loan.fixed_months = None, None, 0
    if archived is not None:
        loan.archived_at = clock.now() if archived else None
    db.commit()
    return _out(db, loan)


@router.delete("/loans/{loan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_loan(loan_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Response:
    db.delete(get_owned_or_404(db, Loan, loan_id, user))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/loans/{loan_id}/schedule")
def loan_schedule(loan_id: uuid.UUID, user: CurrentUser, db: DbSession) -> list[InstallmentOut]:
    """The amortization table, recalculated with every review and early repayment."""
    loan = get_owned_or_404(db, Loan, loan_id, user)
    today = clock.today()
    rows, rates = loans.table(db, loan, today)
    reviews = {number for number, *_ in rates.reviews}
    return [_installment(row, today, row.number in reviews) for row in rows]


def _installment(row: Installment, today: dt.date, review: bool) -> InstallmentOut:
    return InstallmentOut(
        number=row.number,
        date=row.date,
        rate=row.rate,
        payment=row.payment,
        interest=row.interest,
        principal=row.principal,
        outstanding=row.outstanding,
        paid=row.date <= today,
        review=review,
    )


# --- Early repayment --------------------------------------------------------------------------


@router.post("/loans/{loan_id}/simulate")
def simulate(
    loan_id: uuid.UUID, body: SimulationIn, user: CurrentUser, db: DbSession
) -> SimulationOut:
    """What an early repayment would cost and save. Stores nothing."""
    loan = get_owned_or_404(db, Loan, loan_id, user)
    result = loans.simulate(db, loan, clock.today(), body.date, body.amount, body.mode)
    return SimulationOut(**result.__dict__)


@router.get("/loans/{loan_id}/prepayments")
def list_prepayments(loan_id: uuid.UUID, user: CurrentUser, db: DbSession) -> list[PrepaymentOut]:
    get_owned_or_404(db, Loan, loan_id, user)
    rows = db.scalars(
        owned(LoanPrepayment, user)
        .where(LoanPrepayment.loan_id == loan_id)
        .order_by(LoanPrepayment.date)
    )
    return [
        PrepaymentOut(id=r.id, date=r.date, amount=r.amount, mode=r.mode, fee=r.fee) for r in rows
    ]


@router.post("/loans/{loan_id}/prepayments", status_code=status.HTTP_201_CREATED)
def add_prepayment(
    loan_id: uuid.UUID, body: SimulationIn, user: CurrentUser, db: DbSession
) -> LoanOut:
    """Record an early repayment: the table is recalculated from it on."""
    loan = get_owned_or_404(db, Loan, loan_id, user)
    today = clock.today()
    rows, _ = loans.table(db, loan, today)
    outstanding = next(
        (r.outstanding for r in reversed(rows) if r.date < body.date), loan.principal
    )
    if body.amount > outstanding:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Es más de lo que queda por pagar en esa fecha.",
        )
    fee, _, _ = loans.fee_for(loan, rows, body.date, body.amount)
    db.add(
        LoanPrepayment(
            user_id=user.id,
            loan_id=loan.id,
            date=body.date,
            amount=body.amount,
            mode=body.mode,
            fee=fee,
            created_at=clock.now(),
        )
    )
    db.commit()
    return _out(db, loan)


@router.delete(
    "/loans/{loan_id}/prepayments/{prepayment_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_prepayment(
    loan_id: uuid.UUID, prepayment_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> Response:
    row = get_owned_or_404(db, LoanPrepayment, prepayment_id, user)
    if row.loan_id != loan_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Reference index --------------------------------------------------------------------------


@router.get("/reference-rates")
def list_reference_rates(
    user: CurrentUser, db: DbSession, index: Index = "euribor_12m"
) -> list[ReferenceRateOut]:
    """Monthly values, newest first. Shared by everyone: it is public data."""
    rows = db.scalars(
        select(ReferenceRate)
        .where(ReferenceRate.index == index)
        .order_by(ReferenceRate.month.desc())
    )
    return [ReferenceRateOut(id=r.id, index=r.index, month=r.month, value=r.value) for r in rows]


@router.put("/reference-rates")
def set_reference_rate(body: ReferenceRateIn, user: CurrentUser, db: DbSession) -> ReferenceRateOut:
    if not Decimal(-5) <= body.value <= Decimal(20):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Ese valor no parece un Euribor."
        )
    month = body.month.replace(day=1)
    row = db.scalar(
        select(ReferenceRate).where(ReferenceRate.index == body.index, ReferenceRate.month == month)
    )
    if row is None:
        row = ReferenceRate(index=body.index, month=month, value=body.value, updated_by=user.id)
        db.add(row)
    else:
        row.value, row.updated_by = body.value, user.id
    db.commit()
    return ReferenceRateOut(id=row.id, index=body.index, month=row.month, value=row.value)


@router.delete("/reference-rates/{rate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reference_rate(rate_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Response:
    """Only whoever typed it in, or an administrator: everyone's loans use it."""
    row = db.get(ReferenceRate, rate_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if row.updated_by != user.id and not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo quien lo introdujo puede borrarlo.")
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app import clock
from app.db import Base
from app.models.accounts import MONEY, RATE
from app.models.base import OwnedMixin

LOAN_KINDS = (
    "mortgage",  # hipoteca
    "personal",
    "car",
    "consumer",  # financiación al consumo
    "credit_line",
    "p2p_owe",  # préstamo entre particulares: debo
    "p2p_lent",  # préstamo entre particulares: me deben
)
RATE_TYPES = ("fixed", "variable", "mixed")
SYSTEMS = ("french", "linear")
INDEXES = ("euribor_12m",)


class Loan(OwnedMixin, Base):
    """A loan or mortgage (RF-PRE-01…03). Its amortization table is derived from these terms,
    the reference index values and the early repayments; nothing of it is stored."""

    __tablename__ = "loans"
    __table_args__ = (
        CheckConstraint(f"kind IN {LOAN_KINDS}", name="kind_valid"),
        CheckConstraint(f"rate_type IN {RATE_TYPES}", name="rate_type_valid"),
        CheckConstraint(f"system IN {SYSTEMS}", name="system_valid"),
        CheckConstraint("principal > 0", name="principal_positive"),
        CheckConstraint("term_months > 0", name="term_positive"),
        CheckConstraint("grace_months >= 0 AND grace_months < term_months", name="grace_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(60))
    kind: Mapped[str] = mapped_column(String(12))
    lender: Mapped[str | None] = mapped_column(String(60), doc="Bank or person")
    principal: Mapped[Decimal] = mapped_column(MONEY)
    signed_on: Mapped[dt.date] = mapped_column(Date)
    first_payment: Mapped[dt.date] = mapped_column(Date)
    term_months: Mapped[int]
    system: Mapped[str] = mapped_column(String(8), default="french")
    grace_months: Mapped[int] = mapped_column(default=0)
    rate_type: Mapped[str] = mapped_column(String(8), default="fixed")
    # Fixed loans: the TIN. Variable and mixed: the rate of the initial fixed period.
    fixed_rate: Mapped[Decimal] = mapped_column(RATE)
    fixed_months: Mapped[int] = mapped_column(
        default=0, doc="Variable/mixed: months at the fixed rate before the first review"
    )
    index: Mapped[str | None] = mapped_column(String(16))
    spread: Mapped[Decimal | None] = mapped_column(RATE, doc="Diferencial over the index")
    review_months: Mapped[int] = mapped_column(SmallInteger, default=12)
    tae: Mapped[Decimal | None] = mapped_column(RATE)
    opening_fee: Mapped[Decimal | None] = mapped_column(MONEY)
    early_repayment_fee: Mapped[Decimal] = mapped_column(
        RATE, default=Decimal(0), doc="Percent in the contract"
    )
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), index=True
    )
    note: Mapped[str | None] = mapped_column(Text)
    archived_at: Mapped[dt.datetime | None]
    created_at: Mapped[dt.datetime] = mapped_column(default=clock.now)


class LoanPrepayment(OwnedMixin, Base):
    """An early repayment (RF-PRE-07), with the fee paid for it."""

    __tablename__ = "loan_prepayments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("mode IN ('reduce_payment', 'reduce_term')", name="mode_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    loan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("loans.id", ondelete="CASCADE"), index=True
    )
    date: Mapped[dt.date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    mode: Mapped[str] = mapped_column(String(16))
    fee: Mapped[Decimal] = mapped_column(MONEY, default=Decimal(0))
    created_at: Mapped[dt.datetime] = mapped_column(default=clock.now)


class ReferenceRate(Base):
    """Monthly value of a reference index (Euribor 12 months), typed in by hand and shared by
    every user: it is public data. Automatic updates come later (RF-PRE-06, F2)."""

    __tablename__ = "reference_rates"
    __table_args__ = (UniqueConstraint("index", "month"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    index: Mapped[str] = mapped_column(String(16))
    month: Mapped[dt.date] = mapped_column(Date, doc="First day of the month")
    value: Mapped[Decimal] = mapped_column(RATE)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_at: Mapped[dt.datetime] = mapped_column(default=clock.now, onupdate=clock.now)

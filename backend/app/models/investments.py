import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app import clock
from app.db import Base
from app.models.accounts import MONEY
from app.models.base import OwnedMixin, TimestampMixin

INVESTMENT_KINDS = ("fund", "etf", "stock", "pension_plan")
OPERATION_KINDS = ("buy", "sell", "dividend", "fee", "split", "transfer")

# Participaciones and shares: statements give up to six decimals.
UNITS = Numeric(20, 6)
# Valor liquidativo or share price.
PRICE = Numeric(18, 6)


class Investment(OwnedMixin, TimestampMixin, Base):
    """A fund, ETF, share or pension plan (RF-INV-01). What it holds and what it is worth are
    worked out from its operations and prices; nothing of it is stored."""

    __tablename__ = "investments"
    __table_args__ = (
        CheckConstraint(f"kind IN {INVESTMENT_KINDS}", name="kind_valid"),
        # FIFO goes across every account with the same security: one investment per ISIN.
        UniqueConstraint("user_id", "isin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(16))
    isin: Mapped[str | None] = mapped_column(String(12))
    ticker: Mapped[str | None] = mapped_column(String(16))
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"),
        index=True,
        doc="Where it is held: the account its money comes from and goes to",
    )
    note: Mapped[str | None] = mapped_column(Text)
    archived_at: Mapped[dt.datetime | None]


class InvestmentOperation(OwnedMixin, Base):
    """Something that happened to an investment (RF-INV-02). A transfer between funds belongs
    to the source and names the target with the units it received."""

    __tablename__ = "investment_operations"
    __table_args__ = (
        CheckConstraint(f"kind IN {OPERATION_KINDS}", name="kind_valid"),
        CheckConstraint(
            "units >= 0 AND amount >= 0 AND fee >= 0 AND withholding >= 0", name="not_negative"
        ),
        CheckConstraint(
            "(kind = 'transfer') = (target_investment_id IS NOT NULL)", name="transfer_target"
        ),
        CheckConstraint(
            "(kind = 'split') = (split_from IS NOT NULL AND split_to IS NOT NULL)",
            name="split_ratio",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    investment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("investments.id", ondelete="CASCADE"), index=True
    )
    date: Mapped[dt.date] = mapped_column(Date)
    kind: Mapped[str] = mapped_column(String(10))
    units: Mapped[Decimal] = mapped_column(UNITS, default=Decimal(0))
    amount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal(0))
    fee: Mapped[Decimal] = mapped_column(MONEY, default=Decimal(0))
    withholding: Mapped[Decimal] = mapped_column(MONEY, default=Decimal(0))
    # Split: every `split_from` units become `split_to` (2 → 1 for a reverse split).
    split_from: Mapped[int | None] = mapped_column(SmallInteger)
    split_to: Mapped[int | None] = mapped_column(SmallInteger)
    # No cascade: a fund that received a transfer cannot go while the transfer is there. The
    # check runs at the end of the statement, so deleting a whole user still works.
    target_investment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("investments.id"), index=True
    )
    target_units: Mapped[Decimal | None] = mapped_column(UNITS)
    # The money movement it made in an account, if any.
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL")
    )
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(default=clock.now)


class InvestmentPrice(OwnedMixin, Base):
    """A price typed in by hand, with its date (RF-INV-03)."""

    __tablename__ = "investment_prices"
    __table_args__ = (
        UniqueConstraint("investment_id", "date"),
        CheckConstraint("price > 0", name="price_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    investment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("investments.id", ondelete="CASCADE"), index=True
    )
    date: Mapped[dt.date] = mapped_column(Date)
    price: Mapped[Decimal] = mapped_column(PRICE)

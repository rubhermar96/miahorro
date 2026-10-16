import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, CheckConstraint, Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import OwnedMixin, TimestampMixin

ACCOUNT_KINDS = (
    "checking",  # cuenta corriente
    "savings",  # cuenta de ahorro / remunerada
    "deposit",  # depósito a plazo
    "credit_card",
    "cash",
    "wallet",  # Revolut, PayPal…
    "brokerage",  # cuenta de valores
    "crypto",
)
LIQUIDATION_PERIODS = ("daily", "monthly", "quarterly", "semiannual", "annual", "at_maturity")

# Amounts: up to 999 999 999 999,99 with exactly two decimals (RNF-04).
MONEY = Numeric(14, 2)
# Interest rates in percent with four decimals (2,1500 %).
RATE = Numeric(7, 4)


class Account(OwnedMixin, TimestampMixin, Base):
    """Where money is kept (RF-CTA-01, RF-CTA-02). Its balance is the opening balance plus its
    transactions; nothing stores the balance itself, so it can never drift."""

    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint(f"kind IN {ACCOUNT_KINDS}", name="kind_valid"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="currency_code"),
        CheckConstraint("iban_last4 ~ '^[0-9]{4}$'", name="iban_last4_digits"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(60))
    kind: Mapped[str] = mapped_column(String(20))
    institution: Mapped[str | None] = mapped_column(String(60))
    # Only the last four digits: enough to tell accounts apart, useless to anyone else.
    iban_last4: Mapped[str | None] = mapped_column(String(4))
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    opening_balance: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    opening_date: Mapped[date] = mapped_column(Date)
    is_joint: Mapped[bool] = mapped_column(default=False)
    archived_at: Mapped[datetime | None]

    # Fixed-term deposits (RF-CTA-07).
    maturity_date: Mapped[date | None] = mapped_column(Date)
    auto_renew: Mapped[bool] = mapped_column(default=False)
    early_cancellation_note: Mapped[str | None] = mapped_column(String(200))

    rates: Mapped[list[AccountRate]] = relationship(
        back_populates="account",
        order_by="AccountRate.valid_from",
        cascade="all, delete-orphan",
    )


class AccountRate(Base):
    """Remuneration in force from a date (RF-CTA-03, RF-CTA-04). Banks change conditions, so
    every change is a new row and the history is kept.

    `tiers` holds [{"up_to": "10000.00" | null, "rate": "2.0000"}, …] in ascending order; the
    last tier has no upper limit. Amounts and rates are strings, never floats.
    """

    __tablename__ = "account_rates"
    __table_args__ = (
        UniqueConstraint("account_id", "valid_from"),
        CheckConstraint(f"liquidation IN {LIQUIDATION_PERIODS}", name="liquidation_valid"),
        CheckConstraint("withholding >= 0 AND withholding <= 100", name="withholding_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    valid_from: Mapped[date] = mapped_column(Date)
    tiers: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    tae: Mapped[Decimal | None] = mapped_column(RATE)
    liquidation: Mapped[str] = mapped_column(String(16))
    withholding: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("19.00"))

    account: Mapped[Account] = relationship(back_populates="rates")

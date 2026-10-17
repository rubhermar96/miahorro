import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app import clock
from app.db import Base
from app.models.accounts import MONEY
from app.models.base import OwnedMixin


class CaptureToken(OwnedMixin, Base):
    """Personal token for the payment capture endpoint (RF-MOV-17), e.g. the Apple Pay
    Shortcut. Only a keyed hash is stored: the token is shown once, when it is created."""

    __tablename__ = "capture_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(60))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    hint: Mapped[str] = mapped_column(String(8), doc="First characters, to recognise it")
    default_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[dt.datetime] = mapped_column(default=clock.now)
    last_used_at: Mapped[dt.datetime | None]
    revoked_at: Mapped[dt.datetime | None]
    # Simple rate limit: requests in the current window.
    window_start: Mapped[dt.datetime | None]
    window_count: Mapped[int] = mapped_column(default=0)


class CaptureCard(OwnedMixin, Base):
    """Which account a card's payments go to ("Visa Bankinter" → the credit card account)."""

    __tablename__ = "capture_cards"
    __table_args__ = (UniqueConstraint("user_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(80))
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    last_seen_at: Mapped[dt.datetime] = mapped_column(default=clock.now)


FREQUENCIES = ("weekly", "monthly", "quarterly", "semiannual", "yearly")


class RecurringItem(OwnedMixin, Base):
    """An expected income or expense that repeats (RF-MOV-06): payroll, rent, bills, a loan
    instalment. It forecasts the next date and is marked as done when the real movement
    arrives (concept contains the text, amount within the tolerance, date close)."""

    __tablename__ = "recurring_items"
    __table_args__ = (
        CheckConstraint(f"frequency IN {FREQUENCIES}", name="frequency_valid"),
        CheckConstraint("kind IN ('expense', 'income')", name="kind_valid"),
        CheckConstraint("amount > 0", name="amount_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(60))
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(10))
    amount: Mapped[Decimal] = mapped_column(MONEY)
    tolerance: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal(10))  # percent
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL")
    )
    match_text: Mapped[str] = mapped_column(String(60))
    frequency: Mapped[str] = mapped_column(String(12))
    next_date: Mapped[dt.date] = mapped_column(Date)
    last_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL")
    )
    created_at: Mapped[dt.datetime] = mapped_column(default=clock.now)

import datetime as dt
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, CheckConstraint, Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app import clock
from app.db import Base
from app.models.accounts import MONEY
from app.models.base import OwnedMixin


class ImportTemplate(Base):
    """How to read one bank's statement: which column is the date, the concept, the amount…

    Shared by every user (RF-IMP-01): it holds column titles, never movements or personal data.
    """

    __tablename__ = "import_templates"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    mapping: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[dt.datetime] = mapped_column(default=clock.now)


class ImportBatch(OwnedMixin, Base):
    """One imported file, so it can be listed and undone as a whole."""

    __tablename__ = "imports"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(200))
    template_name: Mapped[str | None] = mapped_column(String(60))
    imported: Mapped[int]
    skipped: Mapped[int] = mapped_column(default=0)
    merged: Mapped[int] = mapped_column(default=0, server_default="0")
    date_from: Mapped[dt.date | None] = mapped_column(Date)
    date_to: Mapped[dt.date | None] = mapped_column(Date)
    created_at: Mapped[dt.datetime] = mapped_column(default=clock.now)


class CategoryRule(OwnedMixin, Base):
    """Automatic categorisation (RF-MOV-07): if the concept contains the text (and the other
    conditions hold), the movement gets the category, or becomes a transfer to another own
    account. The first matching rule wins."""

    __tablename__ = "category_rules"
    __table_args__ = (
        CheckConstraint("amount_min IS NULL OR amount_min >= 0", name="amount_min_positive"),
        CheckConstraint(
            "amount_max IS NULL OR amount_min IS NULL OR amount_max >= amount_min",
            name="amount_range_ordered",
        ),
        CheckConstraint(
            "(category_id IS NULL) <> (transfer_account_id IS NULL)", name="one_target"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    match_text: Mapped[str] = mapped_column(String(60))
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), index=True
    )
    # Instead of a category, the movement is money moved to another own account (the monthly
    # credit card bill, savings): it becomes a transfer.
    transfer_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    # Size of the amount, without sign: the category already says expense or income.
    amount_min: Mapped[Decimal | None] = mapped_column(MONEY)
    amount_max: Mapped[Decimal | None] = mapped_column(MONEY)
    position: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[dt.datetime] = mapped_column(default=clock.now)

import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, String, Text, false
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.accounts import MONEY
from app.models.base import OwnedMixin, TimestampMixin

CATEGORY_KINDS = ("expense", "income")
TRANSACTION_KINDS = ("expense", "income", "transfer", "adjustment")
TRANSACTION_SOURCES = ("manual", "import", "capture")


class Category(OwnedMixin, Base):
    """Two-level categories (Vivienda / Alquiler), per user (RF-MOV-02)."""

    __tablename__ = "categories"
    __table_args__ = (CheckConstraint(f"kind IN {CATEGORY_KINDS}", name="kind_valid"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(10))
    icon: Mapped[str | None] = mapped_column(String(8))
    archived_at: Mapped[dt.datetime | None]


class Transaction(OwnedMixin, TimestampMixin, Base):
    """A movement of money in one account (RF-MOV-01, RF-MOV-03, RF-MOV-04).

    The amount carries the sign: negative leaves the account, positive enters it. A transfer
    between own accounts is two rows sharing `transfer_id`; it is neither income nor expense.
    """

    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount <> 0", name="amount_not_zero"),
        CheckConstraint(f"kind IN {TRANSACTION_KINDS}", name="kind_valid"),
        CheckConstraint(f"source IN {TRANSACTION_SOURCES}", name="source_valid"),
        CheckConstraint(
            "(kind = 'expense' AND amount < 0) OR (kind = 'income' AND amount > 0)"
            " OR kind IN ('transfer', 'adjustment')",
            name="sign_matches_kind",
        ),
        CheckConstraint(
            "(kind = 'transfer') = (transfer_id IS NOT NULL)", name="transfer_has_pair"
        ),
        Index("ix_transactions_user_id_date", "user_id", "date"),
        Index("ix_transactions_account_id_import_key", "account_id", "import_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    date: Mapped[dt.date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    description: Mapped[str] = mapped_column(String(140))
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), index=True
    )
    note: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(40)), default=list)
    kind: Mapped[str] = mapped_column(String(12))
    transfer_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    source: Mapped[str] = mapped_column(String(12), default="manual")
    # Imported rows: the file they came from (to undo it) and a fingerprint of the bank's
    # row (date, amount, concept) to recognise it when a later file repeats it.
    import_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("imports.id", ondelete="SET NULL"), index=True
    )
    import_key: Mapped[str | None] = mapped_column(String(64))
    # A captured payment stays pending until a bank statement confirms it.
    pending: Mapped[bool] = mapped_column(default=False, server_default=false())
    # Import that merged a bank row into this movement, or turned it into a transfer leg, so
    # undoing that import can put it back as it was.
    merged_import_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("imports.id", ondelete="SET NULL"), index=True
    )
    paired_import_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("imports.id", ondelete="SET NULL"), index=True
    )

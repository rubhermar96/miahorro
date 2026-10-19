import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app import clock
from app.db import Base
from app.models.accounts import MONEY
from app.models.base import OwnedMixin


class BudgetAssignment(OwnedMixin, Base):
    """Money put on an expense category for a financial month (RF-PRS-02, RF-PRS-03).

    One table for both budget modes, so changing mode loses nothing:
    - limits: the monthly cap for the category; it holds for the following months until a
      later row changes it (0 removes it);
    - zero-based: what is assigned to the category that month only.

    `month` is the first day of the financial month when the row was written.
    """

    __tablename__ = "budget_assignments"
    # In zero-based mode the amount can be negative: money moved out of a category that
    # came from earlier months.
    __table_args__ = (UniqueConstraint("user_id", "month", "category_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    month: Mapped[dt.date] = mapped_column(Date)
    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), index=True
    )
    amount: Mapped[Decimal] = mapped_column(MONEY)
    updated_at: Mapped[dt.datetime] = mapped_column(default=clock.now, onupdate=clock.now)

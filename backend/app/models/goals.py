import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app import clock
from app.db import Base
from app.models.accounts import MONEY
from app.models.base import OwnedMixin

PRIORITIES = (1, 2, 3)  # alta, media, baja


class SavingsGoal(OwnedMixin, Base):
    """Something to save for (RF-OBJ-01): "Entrada del piso: 60.000 € para 2029".

    It is funded in two ways (RF-OBJ-03), which can be combined:
    - whole accounts (GoalAccount): everything in them counts towards the goal;
    - virtual piggy banks (GoalContribution): money set aside inside an account, which the
      account then shows as reserved instead of available.

    Setting money aside is the same idea as assigning money in a zero-based budget
    (iteration 6): there, "to assign" will be the available money (balance - reserved) minus
    what is assigned to categories.
    """

    __tablename__ = "savings_goals"
    __table_args__ = (
        CheckConstraint("target_amount > 0", name="target_positive"),
        CheckConstraint(f"priority IN {PRIORITIES}", name="priority_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(60))
    target_amount: Mapped[Decimal] = mapped_column(MONEY)
    target_date: Mapped[dt.date | None] = mapped_column(Date)
    priority: Mapped[int] = mapped_column(SmallInteger, default=2)
    icon: Mapped[str | None] = mapped_column(String(8))
    note: Mapped[str | None] = mapped_column(Text)
    achieved_at: Mapped[dt.datetime | None]
    created_at: Mapped[dt.datetime] = mapped_column(default=clock.now)


class GoalAccount(Base):
    """An account whose whole balance belongs to a goal (a savings account just for it)."""

    __tablename__ = "goal_accounts"

    goal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("savings_goals.id", ondelete="CASCADE"), primary_key=True
    )
    # An account can be whole for one goal only.
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True, unique=True
    )


class GoalContribution(OwnedMixin, Base):
    """Money set aside for a goal inside an account (positive), or taken back (negative)."""

    __tablename__ = "goal_contributions"
    __table_args__ = (CheckConstraint("amount <> 0", name="amount_not_zero"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    goal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("savings_goals.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    date: Mapped[dt.date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    note: Mapped[str | None] = mapped_column(String(140))
    created_at: Mapped[dt.datetime] = mapped_column(default=clock.now)

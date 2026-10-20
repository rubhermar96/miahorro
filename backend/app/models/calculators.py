import datetime as dt
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, CheckConstraint, Date, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app import clock
from app.db import Base
from app.models.base import OwnedMixin, TimestampMixin

CALCULATORS = (
    "compound",
    "savings_goal",
    "mortgage",
    "home",
    "car",
    "personal_loan",
    "emergency",
)


class ReferenceValue(Base):
    """A value of a shared reference table (RF-PLT-02): a tax rate by region, a tax scale, an
    estimated cost. Each one says since when it applies and where it comes from; a change is
    a new row with a later `valid_from`, so past results can still be explained."""

    __tablename__ = "reference_values"
    __table_args__ = (
        UniqueConstraint("table_name", "key", "valid_from"),
        CheckConstraint("length(trim(source)) > 0", name="source_given"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    table_name: Mapped[str] = mapped_column(String(24), doc="itp, ajd, vat, savings_tax…")
    key: Mapped[str] = mapped_column(String(40), doc="Region, or the item of the table")
    value: Mapped[Decimal] = mapped_column(Numeric(14, 4), doc="Percent, or euros")
    # {"brackets": [{"up_to": "300000", "rate": "8"}, {"up_to": null, "rate": "10"}],
    #  "marginal": true}: a scale instead of a single rate.
    extra: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    valid_from: Mapped[dt.date] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(300))
    note: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[dt.datetime] = mapped_column(default=clock.now, onupdate=clock.now)

    def __str__(self) -> str:
        return f"{self.table_name} · {self.key} · {self.valid_from:%d/%m/%Y}"


class CalculatorScenario(OwnedMixin, TimestampMixin, Base):
    """The inputs of a calculation, saved to come back to it or compare it (RF-CAL). The
    results are not stored: they are worked out again with the reference values in force."""

    __tablename__ = "calculator_scenarios"
    __table_args__ = (
        CheckConstraint(f"calculator IN {CALCULATORS}", name="calculator_valid"),
        Index("ix_calculator_scenarios_user_id_calculator", "user_id", "calculator"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    calculator: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(60))
    inputs: Mapped[dict[str, Any]] = mapped_column(JSON)

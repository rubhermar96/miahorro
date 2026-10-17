import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import TimestampMixin

THEMES = ("system", "light", "dark")
LANGUAGES = ("es",)
CURRENCIES = ("EUR", "USD", "GBP", "CHF")


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("email = lower(email)", name="email_lowercase"),
        CheckConstraint("month_start_day BETWEEN 1 AND 28", name="month_start_day_range"),
        CheckConstraint(f"theme IN {THEMES}", name="theme_valid"),
        CheckConstraint(
            "savings_rate_target IS NULL OR savings_rate_target BETWEEN 1 AND 90",
            name="savings_rate_target_range",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True)

    # Second factor. The secret is encrypted at rest (RNF-05); it stays pending until confirmed.
    totp_secret_encrypted: Mapped[str | None] = mapped_column(Text)
    totp_enabled_at: Mapped[datetime | None]
    totp_last_used_step: Mapped[int | None] = mapped_column(BigInteger)

    # Lockout after repeated failures.
    failed_login_attempts: Mapped[int] = mapped_column(default=0)
    locked_until: Mapped[datetime | None]

    # Preferences (RF-USR-04).
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    month_start_day: Mapped[int] = mapped_column(SmallInteger, default=1)
    # Share of income to save each financial month, in percent (RF-OBJ-06); None: not set.
    savings_rate_target: Mapped[int | None] = mapped_column(SmallInteger)
    theme: Mapped[str] = mapped_column(String(10), default="system")
    language: Mapped[str] = mapped_column(String(5), default="es")

    # Default categories are created once, the first time they are needed.
    categories_seeded_at: Mapped[datetime | None]

    @property
    def has_totp(self) -> bool:
        return self.totp_enabled_at is not None

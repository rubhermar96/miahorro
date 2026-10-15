import uuid
from datetime import datetime

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from app import clock


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(default=clock.now)
    updated_at: Mapped[datetime] = mapped_column(default=clock.now, onupdate=clock.now)


class OwnedMixin:
    """Rows that belong to one user. Read them through app.ownership, never with a bare query,
    so one user can never reach another's data (RF-PLT-01)."""

    @declared_attr
    def user_id(cls) -> Mapped[uuid.UUID]:  # noqa: N805  # SQLAlchemy passes the class
        return mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

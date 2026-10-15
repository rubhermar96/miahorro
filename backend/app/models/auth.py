import uuid
from datetime import datetime

from sqlalchemy import JSON, ForeignKey, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app import clock
from app.db import Base
from app.models.base import OwnedMixin
from app.models.user import User

# Session levels: a password login stays "pending" until the second factor is given, and a
# user without one must set it up ("setup") before reaching anything else.
LEVEL_FULL = "full"
LEVEL_MFA_PENDING = "mfa_pending"
LEVEL_MFA_SETUP = "mfa_setup"


class AuthSession(Base):
    """A signed-in device. The cookie holds a random token; only its SHA-256 is stored."""

    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    level: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(default=clock.now)
    last_seen_at: Mapped[datetime] = mapped_column(default=clock.now)
    idle_expires_at: Mapped[datetime]
    expires_at: Mapped[datetime]
    user_agent: Mapped[str | None] = mapped_column(String(200))

    user: Mapped[User] = relationship(lazy="joined")


class RecoveryCode(OwnedMixin, Base):
    """Single-use codes to sign in without the authenticator app; stored as HMACs."""

    __tablename__ = "recovery_codes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code_hash: Mapped[str] = mapped_column(String(64))
    used_at: Mapped[datetime | None]


class PasskeyCredential(OwnedMixin, Base):
    __tablename__ = "passkeys"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    credential_id: Mapped[bytes] = mapped_column(LargeBinary, unique=True)
    public_key: Mapped[bytes] = mapped_column(LargeBinary)
    sign_count: Mapped[int] = mapped_column(default=0)
    transports: Mapped[list[str]] = mapped_column(JSON, default=list)
    name: Mapped[str] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(default=clock.now)
    last_used_at: Mapped[datetime | None]


class AuthChallenge(Base):
    """One-time WebAuthn challenge, valid for a few minutes."""

    __tablename__ = "auth_challenges"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    purpose: Mapped[str] = mapped_column(String(32))
    challenge: Mapped[bytes] = mapped_column(LargeBinary)
    expires_at: Mapped[datetime]

    def is_valid_for(self, purpose: str, user_id: uuid.UUID | None, at: datetime) -> bool:
        return self.purpose == purpose and self.user_id == user_id and at < self.expires_at

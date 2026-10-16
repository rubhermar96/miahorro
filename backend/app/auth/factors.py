"""Which second factors a user has (D23).

A passkey (Face ID) or an authenticator app (TOTP) both count. Without either, the next
password sign-in asks to set one up.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.auth import PasskeyCredential, RecoveryCode
from app.models.user import User


def passkey_count(db: Session, user: User) -> int:
    query = select(func.count()).where(PasskeyCredential.user_id == user.id)
    return db.scalar(query) or 0


def recovery_codes_left(db: Session, user: User) -> int:
    query = select(func.count()).where(
        RecoveryCode.user_id == user.id, RecoveryCode.used_at.is_(None)
    )
    return db.scalar(query) or 0


def has_second_factor(db: Session, user: User) -> bool:
    return user.has_totp or passkey_count(db, user) > 0

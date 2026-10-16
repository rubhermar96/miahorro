import hashlib
import secrets
import uuid
from datetime import timedelta

from fastapi import Response
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app import clock
from app.config import Settings
from app.models.auth import LEVEL_FULL, AuthSession
from app.models.user import User

# A half-finished sign-in (second factor pending or being set up) expires quickly.
_PENDING_LIFETIME = timedelta(minutes=15)
# Avoid a database write on every request: refresh "last seen" at most this often.
_TOUCH_INTERVAL = timedelta(minutes=5)


def _token_id(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create(db: Session, user: User, level: str, settings: Settings, user_agent: str | None) -> str:
    """Store a new session and return the token for the cookie."""
    token = secrets.token_urlsafe(32)
    now = clock.now()
    if level == LEVEL_FULL:
        idle_expires = now + timedelta(days=settings.session_idle_days)
        expires = now + timedelta(days=settings.session_max_days)
    else:
        idle_expires = expires = now + _PENDING_LIFETIME
    db.add(
        AuthSession(
            id=_token_id(token),
            user_id=user.id,
            level=level,
            created_at=now,
            last_seen_at=now,
            idle_expires_at=min(idle_expires, expires),
            expires_at=expires,
            user_agent=(user_agent or "")[:200] or None,
        )
    )
    return token


def load(db: Session, token: str | None, settings: Settings) -> AuthSession | None:
    """Return the live session for a cookie token; expired sessions are deleted."""
    if not token:
        return None
    row = db.get(AuthSession, _token_id(token))
    if row is None:
        return None
    now = clock.now()
    if now >= row.idle_expires_at or now >= row.expires_at or not row.user.is_active:
        db.delete(row)
        db.commit()
        return None
    if row.level == LEVEL_FULL and now - row.last_seen_at >= _TOUCH_INTERVAL:
        row.last_seen_at = now
        row.idle_expires_at = min(now + timedelta(days=settings.session_idle_days), row.expires_at)
        db.commit()
    return row


def revoke(db: Session, row: AuthSession) -> None:
    db.delete(row)


def revoke_all(db: Session, user_id: uuid.UUID) -> None:
    db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))


def set_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_max_days * 24 * 3600,
        path="/",
        secure=settings.secure_cookies,
        httponly=True,
        samesite="lax",
    )


def clear_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        secure=settings.secure_cookies,
        httponly=True,
        samesite="lax",
    )

"""Temporary lockout after repeated wrong passwords or codes."""

import math
from datetime import timedelta

from fastapi import HTTPException, status

from app import clock
from app.config import Settings
from app.models.user import User


def ensure_not_locked(user: User) -> None:
    now = clock.now()
    if user.locked_until is not None and user.locked_until > now:
        minutes = math.ceil((user.locked_until - now).total_seconds() / 60)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Demasiados intentos fallidos. Vuelve a intentarlo en {minutes} min.",
            headers={"Retry-After": str(minutes * 60)},
        )


def register_failure(user: User, settings: Settings) -> None:
    user.failed_login_attempts += 1
    if user.failed_login_attempts >= settings.login_max_attempts:
        user.locked_until = clock.now() + timedelta(minutes=settings.login_lockout_minutes)
        user.failed_login_attempts = 0


def register_success(user: User) -> None:
    user.failed_login_attempts = 0
    user.locked_until = None

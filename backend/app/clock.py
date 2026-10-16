"""Single source of the current time, so tests can move it forward (sessions, lockouts, TOTP)."""

from datetime import UTC, datetime


def now() -> datetime:
    return datetime.now(UTC)

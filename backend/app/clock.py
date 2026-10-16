"""Single source of the current time, so tests can move it forward (sessions, lockouts, TOTP)."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

# Dates the user sees ("today", a transaction's day) are Spanish dates.
LOCAL_TZ = ZoneInfo("Europe/Madrid")


def now() -> datetime:
    return datetime.now(UTC)


def today() -> date:
    return now().astimezone(LOCAL_TZ).date()

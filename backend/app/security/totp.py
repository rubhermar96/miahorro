"""Time-based one-time codes (authenticator apps such as Google Authenticator or 1Password)."""

import hmac
from datetime import datetime

import pyotp
import segno

ISSUER = "MiAhorro"
# Accept the previous and next 30-second window to tolerate clock drift on the phone.
_DRIFT_STEPS = 1


def new_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=ISSUER)


def qr_data_uri(uri: str) -> str:
    return str(segno.make(uri, error="m").svg_data_uri(scale=6, border=2))


def normalise(code: str) -> str:
    return code.replace(" ", "").replace("-", "").strip()


def verify(secret: str, code: str, at: datetime, last_used_step: int | None) -> int | None:
    """Return the time step the code belongs to, or None if it is wrong or already used.

    Remembering the last used step stops the same code from being replayed.
    """
    code = normalise(code)
    if len(code) != 6 or not code.isdigit():
        return None
    totp = pyotp.TOTP(secret)
    current = totp.timecode(at)
    for step in range(current - _DRIFT_STEPS, current + _DRIFT_STEPS + 1):
        if last_used_step is not None and step <= last_used_step:
            continue
        if hmac.compare_digest(totp.generate_otp(step), code):
            return step
    return None

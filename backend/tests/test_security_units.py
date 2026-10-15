from datetime import UTC, datetime, timedelta

import pyotp
import pytest
from cryptography.fernet import InvalidToken

from app.security import encryption, passwords, recovery, totp

KEY = "unit-test-secret-key-0000000000000000000"
NOW = datetime(2026, 10, 15, 10, 0, tzinfo=UTC)


def test_passwords_round_trip_with_argon2() -> None:
    hashed = passwords.hash_password("una contraseña larga")

    assert hashed.startswith("$argon2id$")
    assert passwords.verify_password("una contraseña larga", hashed)[0] is True
    assert passwords.verify_password("otra", hashed)[0] is False
    assert passwords.verify_password("lo que sea", None) == (False, None)


@pytest.mark.parametrize(("password", "ok"), [("x" * 11, False), ("x" * 12, True)])
def test_new_password_minimum_length(password: str, ok: bool) -> None:
    if ok:
        passwords.validate_new_password(password)
    else:
        with pytest.raises(ValueError, match="12 caracteres"):
            passwords.validate_new_password(password)


def test_encryption_round_trip_and_key_binding() -> None:
    token = encryption.encrypt(KEY, "JBSWY3DPEHPK3PXP")

    assert "JBSWY3DPEHPK3PXP" not in token
    assert encryption.decrypt(KEY, token) == "JBSWY3DPEHPK3PXP"
    with pytest.raises(InvalidToken):
        encryption.decrypt("another-key-0000000000000000000000000000", token)


def test_totp_accepts_drift_of_one_window_only() -> None:
    secret = totp.new_secret()
    otp = pyotp.TOTP(secret)

    assert totp.verify(secret, otp.at(NOW), NOW, None) is not None
    assert totp.verify(secret, otp.at(NOW - timedelta(seconds=30)), NOW, None) is not None
    assert totp.verify(secret, otp.at(NOW + timedelta(seconds=30)), NOW, None) is not None
    assert totp.verify(secret, otp.at(NOW - timedelta(seconds=90)), NOW, None) is None


def test_totp_rejects_replays_and_garbage() -> None:
    secret = totp.new_secret()
    code = pyotp.TOTP(secret).at(NOW)
    step = totp.verify(secret, code, NOW, None)

    assert step is not None
    assert totp.verify(secret, code, NOW, step) is None
    assert totp.verify(secret, f"{code[:3]} {code[3:]}", NOW, None) == step  # spaces are fine
    for garbage in ["", "12345", "1234567", "abcdef"]:
        assert totp.verify(secret, garbage, NOW, None) is None


def test_recovery_codes_are_readable_and_normalised() -> None:
    codes = recovery.new_codes()

    assert len(codes) == 10
    assert all(len(code) == 11 and code[5] == "-" for code in codes)
    assert not set("".join(codes)) & set("01ilo")
    assert recovery.hash_code(KEY, codes[0]) == recovery.hash_code(
        KEY, codes[0].upper().replace("-", " ")
    )

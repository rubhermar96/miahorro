import uuid
from datetime import datetime

import pyotp
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import clock
from app.models.user import User
from app.security import encryption, totp
from app.security.passwords import hash_password

PASSWORD = "una-contraseña-larga-de-prueba"


def create_user(
    app: FastAPI,
    email: str = "ana@example.com",
    *,
    password: str = PASSWORD,
    admin: bool = False,
    with_totp: bool = False,
    active: bool = True,
) -> tuple[uuid.UUID, str | None]:
    """Create a user directly in the database. Returns (id, TOTP secret or None)."""
    secret_key = app.state.settings.secret_key.get_secret_value()
    secret = totp.new_secret() if with_totp else None
    with app.state.session_factory() as db:
        user = User(
            email=email,
            display_name=email.split("@")[0].title(),
            password_hash=hash_password(password),
            is_admin=admin,
            is_active=active,
            totp_secret_encrypted=encryption.encrypt(secret_key, secret) if secret else None,
            totp_enabled_at=clock.now() if secret else None,
        )
        db.add(user)
        db.commit()
        return user.id, secret


def totp_code(secret: str, at: datetime | None = None) -> str:
    return pyotp.TOTP(secret).at(at or clock.now())


def sign_in(client: TestClient, email: str, secret: str, password: str = PASSWORD) -> None:
    """Complete password + TOTP sign-in. Advance the fake clock between calls (codes are
    single use)."""
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.json() == {"status": "mfa_required"}, response.text
    response = client.post("/api/auth/mfa", json={"code": totp_code(secret)})
    assert response.json() == {"status": "authenticated"}, response.text

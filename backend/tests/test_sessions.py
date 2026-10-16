"""Session cookie, expiry, sign-out and CSRF protection."""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.csrf import CSRF_HEADER
from app.main import create_app
from tests.conftest import FakeClock, make_settings, new_client
from tests.helpers import PASSWORD, create_user, sign_in, totp_code


@pytest.fixture
def signed_in(app: FastAPI, client: TestClient, fake_clock: FakeClock) -> str:
    _, secret = create_user(app, with_totp=True)
    assert secret
    sign_in(client, "ana@example.com", secret)
    fake_clock.advance(seconds=30)
    return secret


def _set_cookie_header(client: TestClient, secret: str) -> str:
    """Sign in and return the Set-Cookie header of the final (full) session."""
    client.post("/api/auth/login", json={"email": "ana@example.com", "password": PASSWORD})
    response = client.post("/api/auth/mfa", json={"code": totp_code(secret)})
    return response.headers["set-cookie"]


def test_development_cookie_is_httponly_and_samesite(
    app: FastAPI, client: TestClient, fake_clock: FakeClock
) -> None:
    _, secret = create_user(app, with_totp=True)
    assert secret

    header = _set_cookie_header(client, secret)

    assert header.startswith("miahorro_session=")
    assert "HttpOnly" in header
    assert "SameSite=lax" in header
    assert "Path=/" in header
    assert "Secure" not in header  # Safari would drop it over plain http
    assert "Domain" not in header


@pytest.fixture
def production_app(migrated_database: str) -> Iterator[FastAPI]:
    application = create_app(
        make_settings(
            environment="production",
            database_url=migrated_database,
            public_url="https://miahorro.example.com",
        )
    )
    yield application
    application.state.engine.dispose()


def test_production_cookie_is_host_only_and_secure(
    app: FastAPI, production_app: FastAPI, fake_clock: FakeClock
) -> None:
    _, secret = create_user(app, with_totp=True)
    assert secret

    with new_client(production_app, base_url="https://testserver") as client:
        header = _set_cookie_header(client, secret)

    assert header.startswith("__Host-miahorro_session=")
    assert "Secure" in header
    assert "HttpOnly" in header
    assert "Domain" not in header


def test_session_expires_after_a_month_without_use(
    client: TestClient, signed_in: str, fake_clock: FakeClock
) -> None:
    fake_clock.advance(days=29)
    assert client.get("/api/me").status_code == 200  # using it extends it

    fake_clock.advance(days=29)
    assert client.get("/api/me").status_code == 200

    fake_clock.advance(days=31)
    assert client.get("/api/me").status_code == 401


def test_session_ends_after_ninety_days_even_if_used(
    client: TestClient, signed_in: str, fake_clock: FakeClock
) -> None:
    for _ in range(4):
        fake_clock.advance(days=22)
        assert client.get("/api/me").status_code == 200

    fake_clock.advance(days=3)  # 91 days after signing in
    assert client.get("/api/me").status_code == 401


def test_logout_ends_the_session(client: TestClient, signed_in: str) -> None:
    response = client.post("/api/auth/logout")

    assert response.status_code == 204
    assert 'miahorro_session=""' in response.headers["set-cookie"]
    assert client.get("/api/me").status_code == 401


def test_logout_everywhere_ends_every_session(
    app: FastAPI, client: TestClient, signed_in: str, fake_clock: FakeClock
) -> None:
    with new_client(app) as phone:
        sign_in(phone, "ana@example.com", signed_in)
        assert phone.get("/api/me").status_code == 200

        assert client.post("/api/auth/logout-all").status_code == 204

        assert phone.get("/api/me").status_code == 401
        assert client.get("/api/me").status_code == 401


def test_a_stolen_old_cookie_is_useless_after_logout(
    app: FastAPI, client: TestClient, signed_in: str
) -> None:
    old_token = client.cookies.get("miahorro_session")
    client.post("/api/auth/logout")

    with new_client(app) as attacker:
        attacker.cookies.set("miahorro_session", old_token or "")
        assert attacker.get("/api/me").status_code == 401


def test_changes_without_the_anti_csrf_header_are_rejected(
    client: TestClient, signed_in: str
) -> None:
    response = client.patch(
        "/api/me/preferences", json={"theme": "dark"}, headers={CSRF_HEADER: ""}
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    assert client.get("/api/me").json()["preferences"]["theme"] == "system"


def test_reads_do_not_need_the_anti_csrf_header(client: TestClient, signed_in: str) -> None:
    assert client.get("/api/me", headers={CSRF_HEADER: ""}).status_code == 200

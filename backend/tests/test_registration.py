"""Open registration (RF-PLT-03, D22)."""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import create_app
from app.models.user import User
from tests.conftest import FakeClock, _truncate_all, make_settings, new_client
from tests.helpers import PASSWORD, create_user, totp_code


def _register(
    client: TestClient,
    email: str = "ana@example.com",
    name: str = "Ana",
    password: str = PASSWORD,
) -> Any:
    return client.post(
        "/api/auth/register",
        json={"display_name": name, "email": email, "password": password},
    )


def _users(app: FastAPI) -> list[User]:
    with app.state.session_factory() as db:
        return list(db.scalars(select(User).order_by(User.created_at)))


def test_registration_is_open_by_default(client: TestClient) -> None:
    assert client.get("/api/auth/registration").json() == {"open": True}


def test_register_then_set_up_the_second_factor(
    app: FastAPI, client: TestClient, fake_clock: FakeClock
) -> None:
    response = _register(client, email="  Ana@Example.com ", name="  Ana  ")

    assert response.status_code == 201
    assert response.json() == {"status": "mfa_setup_required"}
    assert client.get("/api/auth/session").json()["level"] == "mfa_setup"
    assert client.get("/api/me").status_code == 401  # nothing else until the second factor

    secret = client.post("/api/auth/totp/setup").json()["secret"]
    confirm = client.post("/api/auth/totp/confirm", json={"code": totp_code(secret)})

    assert confirm.status_code == 200
    me = client.get("/api/me").json()
    assert (me["email"], me["display_name"], me["has_totp"]) == ("ana@example.com", "Ana", True)


def test_the_first_account_is_the_administrator(app: FastAPI, client: TestClient) -> None:
    _register(client, email="ana@example.com")
    with new_client(app) as friend:
        _register(friend, email="bea@example.com")

    assert [(u.email, u.is_admin) for u in _users(app)] == [
        ("ana@example.com", True),
        ("bea@example.com", False),
    ]


def test_an_email_can_only_be_used_once(app: FastAPI, client: TestClient) -> None:
    create_user(app, "ana@example.com")

    response = _register(client, email="ANA@example.com")

    assert response.status_code == 409
    assert response.json()["error"]["message"] == "Ya existe una cuenta con ese email."


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("password", "corta", "La contraseña debe tener al menos 12 caracteres."),
        ("email", "no-es-un-email", "El email no es válido."),
        ("name", "   ", "Escribe tu nombre."),
    ],
)
def test_invalid_data_is_explained(
    app: FastAPI, client: TestClient, field: str, value: str, message: str
) -> None:
    response = _register(client, **{field: value})

    assert response.status_code == 422
    assert response.json()["error"]["message"] == message
    assert _users(app) == []


def test_registering_needs_the_anti_csrf_header(app: FastAPI, client: TestClient) -> None:
    response = client.post(
        "/api/auth/register",
        json={"display_name": "Ana", "email": "ana@example.com", "password": PASSWORD},
        headers={"X-MiAhorro-CSRF": ""},
    )

    assert response.status_code == 403
    assert _users(app) == []


@pytest.fixture
def make_app(migrated_database: str) -> Iterator[Any]:
    apps: list[FastAPI] = []

    def factory(**overrides: Any) -> FastAPI:
        application = create_app(make_settings(database_url=migrated_database, **overrides))
        _truncate_all(application.state.engine)
        apps.append(application)
        return application

    yield factory
    for application in apps:
        application.state.engine.dispose()


def test_registration_can_be_closed(make_app: Any) -> None:
    app = make_app(registration_enabled=False)

    with new_client(app) as client:
        assert client.get("/api/auth/registration").json() == {"open": False}
        response = _register(client)

    assert response.status_code == 403
    assert response.json()["error"]["message"] == "El registro de cuentas está cerrado."


def test_registration_closes_when_the_user_cap_is_reached(make_app: Any) -> None:
    app = make_app(max_users=2)

    with new_client(app) as client:
        assert _register(client, email="a@example.com").status_code == 201
    with new_client(app) as client:
        assert _register(client, email="b@example.com").status_code == 201
    with new_client(app) as client:
        assert client.get("/api/auth/registration").json() == {"open": False}
        assert _register(client, email="c@example.com").status_code == 403

    assert len(_users(app)) == 2

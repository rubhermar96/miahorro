"""Passkeys (Face ID): registration, sign-in and ownership."""

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.conftest import FakeClock, new_client
from tests.helpers import create_user, sign_in
from tests.webauthn_soft import SoftPasskey


@pytest.fixture
def ana(app: FastAPI, client: TestClient, fake_clock: FakeClock) -> TestClient:
    _, secret = create_user(app, with_totp=True)
    assert secret
    sign_in(client, "ana@example.com", secret)
    return client


def _register(client: TestClient, passkey: SoftPasskey, name: str = "iPhone de Ana") -> Any:
    options = client.post("/api/auth/passkeys/register/options").json()
    credential = passkey.create(options["options"])
    return client.post(
        "/api/auth/passkeys/register",
        json={"challenge_id": options["challenge_id"], "credential": credential, "name": name},
    )


def _passkey_login(client: TestClient, passkey: SoftPasskey) -> Any:
    options = client.post("/api/auth/passkeys/login/options").json()
    return client.post(
        "/api/auth/passkeys/login",
        json={
            "challenge_id": options["challenge_id"],
            "credential": passkey.get(options["options"]),
        },
    )


def test_registration_options_ask_for_a_discoverable_verified_passkey(ana: TestClient) -> None:
    options = ana.post("/api/auth/passkeys/register/options").json()["options"]

    assert options["rp"] == {"id": "localhost", "name": "MiAhorro"}
    assert options["user"]["name"] == "ana@example.com"
    assert options["authenticatorSelection"]["residentKey"] == "required"
    assert options["authenticatorSelection"]["userVerification"] == "required"


def test_register_a_passkey_and_sign_in_with_it_alone(app: FastAPI, ana: TestClient) -> None:
    passkey = SoftPasskey()

    registered = _register(ana, passkey)

    assert registered.status_code == 201
    assert registered.json()["name"] == "iPhone de Ana"
    assert [p["name"] for p in ana.get("/api/auth/passkeys").json()] == ["iPhone de Ana"]

    with new_client(app) as phone:
        result = _passkey_login(phone, passkey)
        assert result.json() == {"status": "authenticated"}  # no password, no code
        assert phone.get("/api/me").json()["email"] == "ana@example.com"

    assert ana.get("/api/auth/passkeys").json()[0]["last_used_at"] is not None


def test_each_challenge_can_be_answered_only_once(app: FastAPI, ana: TestClient) -> None:
    passkey = SoftPasskey()
    _register(ana, passkey)
    options = ana.post("/api/auth/passkeys/login/options").json()
    body = {"challenge_id": options["challenge_id"], "credential": passkey.get(options["options"])}

    with new_client(app) as phone:
        assert phone.post("/api/auth/passkeys/login", json=body).status_code == 200
    with new_client(app) as attacker:
        assert attacker.post("/api/auth/passkeys/login", json=body).status_code == 401


def test_challenges_expire(app: FastAPI, ana: TestClient, fake_clock: FakeClock) -> None:
    passkey = SoftPasskey()
    _register(ana, passkey)
    options = ana.post("/api/auth/passkeys/login/options").json()
    fake_clock.advance(minutes=6)

    with new_client(app) as phone:
        response = phone.post(
            "/api/auth/passkeys/login",
            json={
                "challenge_id": options["challenge_id"],
                "credential": passkey.get(options["options"]),
            },
        )
    assert response.status_code == 401


def test_unknown_passkeys_are_rejected(app: FastAPI, ana: TestClient) -> None:
    with new_client(app) as stranger:
        assert _passkey_login(stranger, SoftPasskey()).status_code == 401


def test_passkeys_from_another_website_are_rejected(ana: TestClient) -> None:
    passkey = SoftPasskey(origin="https://phishing.example.com")

    assert _register(ana, passkey).status_code == 400


def test_registering_needs_a_full_session(client: TestClient) -> None:
    assert client.post("/api/auth/passkeys/register/options").status_code == 401


def test_users_cannot_see_or_delete_each_others_passkeys(
    app: FastAPI, ana: TestClient, fake_clock: FakeClock
) -> None:
    _register(ana, SoftPasskey())
    ana_passkey_id = ana.get("/api/auth/passkeys").json()[0]["id"]
    _, bea_secret = create_user(app, "bea@example.com", with_totp=True)
    assert bea_secret

    with new_client(app) as bea:
        sign_in(bea, "bea@example.com", bea_secret)
        assert bea.get("/api/auth/passkeys").json() == []
        assert bea.delete(f"/api/auth/passkeys/{ana_passkey_id}").status_code == 404

    assert len(ana.get("/api/auth/passkeys").json()) == 1


def test_deleted_passkeys_stop_working(app: FastAPI, ana: TestClient) -> None:
    passkey = SoftPasskey()
    _register(ana, passkey)
    passkey_id = ana.get("/api/auth/passkeys").json()[0]["id"]

    assert ana.delete(f"/api/auth/passkeys/{passkey_id}").status_code == 204
    with new_client(app) as phone:
        assert _passkey_login(phone, passkey).status_code == 401

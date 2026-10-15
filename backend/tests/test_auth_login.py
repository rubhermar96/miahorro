"""Password + second factor sign-in (RF-USR-01) and lockout."""

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.conftest import FakeClock
from tests.helpers import PASSWORD, create_user, sign_in, totp_code


def _login(client: TestClient, email: str = "ana@example.com", password: str = PASSWORD) -> Any:
    return client.post("/api/auth/login", json={"email": email, "password": password}).json()


def test_wrong_email_and_wrong_password_get_the_same_answer(
    app: FastAPI, client: TestClient
) -> None:
    create_user(app)

    unknown = client.post("/api/auth/login", json={"email": "nadie@example.com", "password": "x"})
    wrong = client.post("/api/auth/login", json={"email": "ana@example.com", "password": "x"})

    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()
    assert wrong.json()["error"]["message"] == "Email o contraseña incorrectos."


def test_email_is_case_insensitive(app: FastAPI, client: TestClient, fake_clock: FakeClock) -> None:
    create_user(app, with_totp=True)

    assert _login(client, email="  ANA@Example.com ") == {"status": "mfa_required"}


def test_first_sign_in_requires_setting_up_the_authenticator(
    app: FastAPI, client: TestClient, fake_clock: FakeClock
) -> None:
    create_user(app)

    assert _login(client) == {"status": "mfa_setup_required"}
    assert client.get("/api/me").status_code == 401  # nothing else until it is set up
    assert client.get("/api/auth/session").json()["level"] == "mfa_setup"

    setup = client.post("/api/auth/totp/setup").json()
    assert setup["otpauth_uri"].startswith("otpauth://totp/MiAhorro:ana%40example.com?secret=")
    assert setup["qr_code"].startswith("data:image/svg+xml")

    assert client.post("/api/auth/totp/confirm", json={"code": "000000"}).status_code == 401
    pending_cookie = client.cookies.get("miahorro_session")

    confirm = client.post("/api/auth/totp/confirm", json={"code": totp_code(setup["secret"])})

    assert confirm.status_code == 200
    codes = confirm.json()["codes"]
    assert len(codes) == 10
    assert len(set(codes)) == 10
    assert client.cookies.get("miahorro_session") != pending_cookie  # new token, new privileges
    me = client.get("/api/me")
    assert me.status_code == 200
    assert me.json()["has_totp"] is True


def test_returning_user_needs_a_valid_code(
    app: FastAPI, client: TestClient, fake_clock: FakeClock
) -> None:
    _, secret = create_user(app, with_totp=True)
    assert secret

    assert _login(client) == {"status": "mfa_required"}
    assert client.get("/api/me").status_code == 401
    wrong = client.post("/api/auth/mfa", json={"code": "123456"})
    assert wrong.status_code == 401
    assert wrong.json()["error"]["message"] == "El código no es correcto."

    ok = client.post("/api/auth/mfa", json={"code": totp_code(secret)})

    assert ok.json() == {"status": "authenticated"}
    assert client.get("/api/me").status_code == 200


def test_a_code_cannot_be_used_twice(
    app: FastAPI, client: TestClient, fake_clock: FakeClock
) -> None:
    _, secret = create_user(app, with_totp=True)
    assert secret
    code = totp_code(secret)
    sign_in(client, "ana@example.com", secret)

    _login(client)
    replay = client.post("/api/auth/mfa", json={"code": code})

    assert replay.status_code == 401


def test_codes_from_the_neighbouring_window_are_accepted(
    app: FastAPI, client: TestClient, fake_clock: FakeClock
) -> None:
    _, secret = create_user(app, with_totp=True)
    assert secret
    previous_window_code = totp_code(secret)
    fake_clock.advance(seconds=30)  # the phone's clock is a little behind

    _login(client)

    assert client.post("/api/auth/mfa", json={"code": previous_window_code}).status_code == 200


def test_recovery_codes_work_once(app: FastAPI, client: TestClient, fake_clock: FakeClock) -> None:
    create_user(app)
    _login(client)
    secret = client.post("/api/auth/totp/setup").json()["secret"]
    codes = client.post("/api/auth/totp/confirm", json={"code": totp_code(secret)}).json()["codes"]
    client.post("/api/auth/logout")

    _login(client)
    first = client.post("/api/auth/mfa", json={"recovery_code": codes[0].upper()})
    client.post("/api/auth/logout")
    _login(client)
    reused = client.post("/api/auth/mfa", json={"recovery_code": codes[0]})

    assert first.json() == {"status": "authenticated"}
    assert reused.status_code == 401


def test_regenerating_recovery_codes_invalidates_the_old_ones(
    app: FastAPI, client: TestClient, fake_clock: FakeClock
) -> None:
    create_user(app)
    _login(client)
    secret = client.post("/api/auth/totp/setup").json()["secret"]
    old = client.post("/api/auth/totp/confirm", json={"code": totp_code(secret)}).json()["codes"]

    new = client.post("/api/auth/recovery-codes").json()["codes"]
    client.post("/api/auth/logout")
    _login(client)

    assert set(old).isdisjoint(new)
    assert client.post("/api/auth/mfa", json={"recovery_code": old[1]}).status_code == 401
    assert client.post("/api/auth/mfa", json={"recovery_code": new[1]}).status_code == 200


def test_cannot_set_up_a_second_authenticator_over_the_first(
    app: FastAPI, client: TestClient, fake_clock: FakeClock
) -> None:
    _, secret = create_user(app, with_totp=True)
    assert secret
    sign_in(client, "ana@example.com", secret)

    assert client.post("/api/auth/totp/setup").status_code == 409


def test_five_wrong_passwords_lock_the_account_for_a_while(
    app: FastAPI, client: TestClient, fake_clock: FakeClock
) -> None:
    create_user(app, with_totp=True)
    for _ in range(5):
        assert (
            client.post(
                "/api/auth/login", json={"email": "ana@example.com", "password": "mal"}
            ).status_code
            == 401
        )

    locked = client.post("/api/auth/login", json={"email": "ana@example.com", "password": PASSWORD})

    assert locked.status_code == 429
    assert locked.headers["retry-after"] == "900"
    assert "15 min" in locked.json()["error"]["message"]

    fake_clock.advance(minutes=15, seconds=1)
    assert _login(client) == {"status": "mfa_required"}


def test_wrong_codes_also_count_towards_the_lockout(
    app: FastAPI, client: TestClient, fake_clock: FakeClock
) -> None:
    _, secret = create_user(app, with_totp=True)
    assert secret
    _login(client)
    for _ in range(5):
        client.post("/api/auth/mfa", json={"code": "000000"})

    response = client.post("/api/auth/mfa", json={"code": totp_code(secret)})

    assert response.status_code == 429


def test_pending_sign_in_expires(app: FastAPI, client: TestClient, fake_clock: FakeClock) -> None:
    _, secret = create_user(app, with_totp=True)
    assert secret
    _login(client)

    fake_clock.advance(minutes=16)

    assert client.post("/api/auth/mfa", json={"code": totp_code(secret)}).status_code == 401


def test_deactivated_users_cannot_sign_in(app: FastAPI, client: TestClient) -> None:
    create_user(app, active=False)

    assert (
        client.post(
            "/api/auth/login", json={"email": "ana@example.com", "password": PASSWORD}
        ).status_code
        == 401
    )

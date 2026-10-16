"""Access control across the whole API and the admin panel."""

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.conftest import FakeClock
from tests.helpers import create_user, sign_in

# The only endpoints reachable without signing in. Any new endpoint is private by default:
# the test below fails if it does not require a session.
PUBLIC_ENDPOINTS = {
    ("GET", "/api/health"),
    ("GET", "/api/auth/registration"),
    ("POST", "/api/auth/register"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/passkeys/login/options"),
    ("POST", "/api/auth/passkeys/login"),
}


def _api_endpoints(app: FastAPI) -> list[tuple[str, str]]:
    # The OpenAPI schema lists every endpoint, however routers are nested.
    return sorted(
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
    )


def test_every_private_endpoint_requires_a_session(app: FastAPI, client: TestClient) -> None:
    private = [e for e in _api_endpoints(app) if e not in PUBLIC_ENDPOINTS]
    assert private, "expected private endpoints"

    for method, path in private:
        url = path.replace("{passkey_id}", str(uuid.uuid4()))
        response = client.request(method, url, json={})
        assert response.status_code == 401, f"{method} {path} -> {response.status_code}"


def test_public_endpoint_list_is_up_to_date(app: FastAPI) -> None:
    assert set(_api_endpoints(app)) >= PUBLIC_ENDPOINTS


@pytest.fixture
def admin_client(app: FastAPI, client: TestClient, fake_clock: FakeClock) -> TestClient:
    _, secret = create_user(app, "admin@example.com", admin=True, with_totp=True)
    assert secret
    sign_in(client, "admin@example.com", secret)
    return client


def test_admin_panel_sends_strangers_to_sign_in(client: TestClient) -> None:
    response = client.get("/admin/", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/entrar?siguiente=/admin"


def test_admin_panel_is_closed_to_regular_users(
    app: FastAPI, client: TestClient, fake_clock: FakeClock
) -> None:
    _, secret = create_user(app, with_totp=True)
    assert secret
    sign_in(client, "ana@example.com", secret)

    assert client.get("/admin/", follow_redirects=False).status_code == 403


def test_admin_panel_lists_users_without_secrets(admin_client: TestClient) -> None:
    page = admin_client.get("/admin/user/list")

    assert page.status_code == 200
    assert "admin@example.com" in page.text
    assert "argon2" not in page.text  # password hashes never shown

"""Profile and preferences (RF-USR-04)."""

from typing import get_args

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.models.user import CURRENCIES, LANGUAGES, THEMES
from app.routers.schemas import Currency, Language, Theme
from tests.conftest import FakeClock, new_client
from tests.helpers import create_user, sign_in


@pytest.fixture
def ana(app: FastAPI, client: TestClient, fake_clock: FakeClock) -> TestClient:
    _, secret = create_user(app, with_totp=True)
    assert secret
    sign_in(client, "ana@example.com", secret)
    return client


def test_profile_includes_default_preferences(ana: TestClient) -> None:
    me = ana.get("/api/me").json()

    assert me["email"] == "ana@example.com"
    assert me["is_admin"] is False
    assert me["preferences"] == {
        "currency": "EUR",
        "month_start_day": 1,
        "theme": "system",
        "language": "es",
        "savings_rate_target": None,
    }


def test_update_some_preferences(ana: TestClient) -> None:
    response = ana.patch("/api/me/preferences", json={"month_start_day": 25, "theme": "dark"})

    assert response.status_code == 200
    assert response.json()["preferences"] == {
        "currency": "EUR",
        "month_start_day": 25,
        "theme": "dark",
        "language": "es",
        "savings_rate_target": None,
    }
    assert ana.get("/api/me").json()["preferences"]["month_start_day"] == 25


@pytest.mark.parametrize(
    "change",
    [
        {"month_start_day": 0},
        {"month_start_day": 29},  # every month has a day 28
        {"theme": "purple"},
        {"currency": "PTS"},
        {"language": "fr"},
    ],
)
def test_invalid_preferences_are_rejected(ana: TestClient, change: dict[str, object]) -> None:
    response = ana.patch("/api/me/preferences", json=change)

    assert response.status_code == 422
    assert ana.get("/api/me").json()["preferences"]["theme"] == "system"


def test_preferences_are_per_user(app: FastAPI, ana: TestClient, fake_clock: FakeClock) -> None:
    _, bea_secret = create_user(app, "bea@example.com", with_totp=True)
    assert bea_secret
    ana.patch("/api/me/preferences", json={"currency": "USD"})

    with new_client(app) as bea:
        sign_in(bea, "bea@example.com", bea_secret)
        assert bea.get("/api/me").json()["preferences"]["currency"] == "EUR"


def test_api_choices_match_the_database_constraints() -> None:
    assert set(get_args(Currency)) == set(CURRENCIES)
    assert set(get_args(Theme)) == set(THEMES)
    assert set(get_args(Language)) == set(LANGUAGES)

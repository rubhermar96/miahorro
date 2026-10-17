"""Payment capture from the phone (RF-MOV-17) and its reconciliation (RF-MOV-09)."""

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import FakeClock, new_client
from tests.test_accounts import new_account
from tests.test_imports import CSV
from tests.test_transactions import category_id

URL = "/api/capture/payments"


@pytest.fixture
def account(ana: TestClient) -> str:
    return str(new_account(ana, opening_date="2026-10-01", opening_balance="100")["id"])


@pytest.fixture
def token(ana: TestClient, account: str) -> str:
    response = ana.post(
        "/api/capture/tokens", json={"name": "iPhone", "default_account_id": account}
    )
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["url"] == URL
    assert created["token"]["hint"] == created["secret"][:8]
    return str(created["secret"])


def pay(app_client: TestClient, token: str, **body: Any) -> Any:
    """As the Shortcut sends it: no session cookie, no CSRF header."""
    phone = new_client(app_client.app)  # type: ignore[arg-type]
    phone.headers.pop("X-MiAhorro-CSRF")
    return phone.post(URL, json=body, headers={"Authorization": f"Bearer {token}"})


def captured(client: TestClient) -> list[tuple[str, str, bool, str]]:
    items = client.get("/api/transactions").json()["items"]
    return [(t["description"], t["amount"], t["pending"], t["source"]) for t in items]


@pytest.mark.parametrize("amount", ["12,50 €", "€12.50", "12.50", 12.5, "12,5"])
def test_a_payment_arrives_as_a_pending_expense(
    ana: TestClient, token: str, amount: str | float
) -> None:
    response = pay(ana, token, amount=amount, merchant="Mercadona", card="Visa Bankinter")

    assert response.status_code == 200, response.text
    assert response.json()["message"] == "Mercadona: 12,50 € en Nómina"
    assert captured(ana) == [("Mercadona", "-12.50", True, "capture")]


def test_rules_categorise_captured_payments(ana: TestClient, token: str) -> None:
    groceries = category_id(ana, "Supermercado")
    ana.post("/api/rules", json={"match_text": "mercadona", "category_id": groceries})

    pay(ana, token, amount="3", merchant="MERCADONA")

    assert ana.get("/api/transactions").json()["items"][0]["category_id"] == groceries


def test_each_card_goes_to_its_account(ana: TestClient, token: str, account: str) -> None:
    pay(ana, token, amount="1", merchant="A", card="Visa")
    card = ana.get("/api/capture/cards").json()[0]
    assert (card["name"], card["account_id"]) == ("Visa", account)

    visa = str(new_account(ana, name="Visa", kind="credit_card")["id"])
    ana.patch(f"/api/capture/cards/{card['id']}", json={"account_id": visa}).raise_for_status()
    pay(ana, token, amount="2", merchant="B", card="visa")  # case does not matter

    items = ana.get("/api/transactions", params={"account_id": visa}).json()["items"]
    assert [t["description"] for t in items] == ["B"]


def test_the_same_payment_sent_twice_is_recorded_once(ana: TestClient, token: str) -> None:
    first = pay(ana, token, amount="4", merchant="Cafe").json()
    again = pay(ana, token, amount="4", merchant="Cafe").json()

    assert (first["status"], again["status"]) == ("recorded", "already_recorded")
    assert len(captured(ana)) == 1


def test_two_identical_coffees_minutes_apart_are_two(
    ana: TestClient, token: str, fake_clock: FakeClock
) -> None:
    pay(ana, token, amount="1,50", merchant="Cafe")
    fake_clock.advance(minutes=30)
    pay(ana, token, amount="1,50", merchant="Cafe")

    assert len(captured(ana)) == 2


def test_the_statement_confirms_the_capture_without_duplicating(
    ana: TestClient, token: str, account: str
) -> None:
    pay(ana, token, amount="45,20", merchant="Mercadona")  # today: 15/10/2026
    statement = b"Fecha;Concepto;Importe\n16/10/2026;COMPRA TARJ. MERCADONA;-45,20\n"

    shown = ana.post(
        "/api/imports/preview",
        data={"account_id": account},
        files={"file": ("e.csv", statement, CSV)},
    ).json()
    assert shown["rows"][0]["status"] == "match"
    ana.post(
        "/api/imports",
        data={
            "account_id": account,
            "mapping": json.dumps(shown["mapping"]),
            "decisions": json.dumps({"2": "merge"}),
        },
        files={"file": ("e.csv", statement, CSV)},
    ).raise_for_status()

    assert captured(ana) == [("Mercadona", "-45.20", False, "capture")]


def test_a_payment_already_imported_is_not_recorded_again(
    ana: TestClient, token: str, account: str
) -> None:
    statement = b"Fecha;Concepto;Importe\n14/10/2026;COMPRA MERCADONA;-45,20\n"
    shown = ana.post(
        "/api/imports/preview", data={"account_id": account}, files={"file": ("e", statement, CSV)}
    ).json()
    ana.post(
        "/api/imports",
        data={
            "account_id": account,
            "mapping": json.dumps(shown["mapping"]),
            "decisions": json.dumps({"2": "import"}),
        },
        files={"file": ("e", statement, CSV)},
    ).raise_for_status()

    late = pay(ana, token, amount="45,20", merchant="Mercadona").json()

    assert late["status"] == "already_recorded"
    assert len(captured(ana)) == 1


def test_unconfirmed_payments_reach_the_review_tray(
    ana: TestClient, token: str, fake_clock: FakeClock
) -> None:
    pay(ana, token, amount="9", merchant="Denegado")
    assert ana.get("/api/inbox").json()["unconfirmed"] == []

    fake_clock.advance(days=8)
    unconfirmed = ana.get("/api/inbox").json()["unconfirmed"]
    assert [t["description"] for t in unconfirmed] == ["Denegado"]

    ana.post(f"/api/transactions/{unconfirmed[0]['id']}/confirm").raise_for_status()
    assert ana.get("/api/inbox").json()["unconfirmed"] == []


def test_a_refund(ana: TestClient, token: str) -> None:
    pay(ana, token, amount="10", merchant="Zara", kind="income")

    assert captured(ana) == [("Zara", "10.00", True, "capture")]


@pytest.mark.parametrize("amount", ["", "doce", "0", "0,00"])
def test_bad_amounts_are_explained(ana: TestClient, token: str, amount: str) -> None:
    response = pay(ana, token, amount=amount, merchant="X")

    assert response.status_code == 422
    assert "Importe no válido" in response.json()["error"]["message"]


def test_wrong_or_revoked_tokens_are_refused(ana: TestClient, token: str) -> None:
    assert pay(ana, "mia_inventado", amount="1").status_code == 401
    assert pay(ana, "", amount="1").status_code == 401

    token_id = ana.get("/api/capture/tokens").json()[0]["id"]
    ana.delete(f"/api/capture/tokens/{token_id}").raise_for_status()

    assert pay(ana, token, amount="1").status_code == 401
    assert ana.get("/api/capture/tokens").json() == []


def test_too_many_payments_in_a_row(ana: TestClient, token: str) -> None:
    for number in range(30):
        pay(ana, token, amount=str(number + 1), merchant=f"Tienda {number}")

    assert pay(ana, token, amount="99", merchant="Una más").status_code == 429


def test_the_session_cookie_does_not_work_on_the_capture_endpoint(ana: TestClient) -> None:
    """Without a token, a signed-in browser cannot post payments (no CSRF header needed here,
    so the cookie must not count)."""
    response = ana.post(URL, json={"amount": "1"})

    assert response.status_code == 401


def test_tokens_and_cards_are_private(ana: TestClient, bea: TestClient, token: str) -> None:
    pay(ana, token, amount="1", card="Visa")

    assert bea.get("/api/capture/tokens").json() == []
    assert bea.get("/api/capture/cards").json() == []
    token_id = ana.get("/api/capture/tokens").json()[0]["id"]
    assert bea.delete(f"/api/capture/tokens/{token_id}").status_code == 404

"""Recurring income and expenses (RF-MOV-06)."""

import datetime as dt
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.recurring import advance
from tests.conftest import FakeClock
from tests.test_accounts import new_account
from tests.test_transactions import add


@pytest.fixture
def account(ana: TestClient) -> str:
    return str(new_account(ana, opening_balance="1000")["id"])


def new_item(client: TestClient, account: str, **fields: Any) -> Any:
    body = {
        "name": "Nómina",
        "account_id": account,
        "kind": "income",
        "amount": "1566.67",
        "match_text": "TRANSF NOMI",
        "frequency": "monthly",
        "next_date": "2026-11-01",
        **fields,
    }
    response = client.post("/api/recurring", json=body)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.parametrize(
    ("date", "frequency", "expected"),
    [
        (dt.date(2026, 1, 31), "monthly", dt.date(2026, 2, 28)),
        (dt.date(2026, 11, 15), "quarterly", dt.date(2027, 2, 15)),
        (dt.date(2026, 10, 15), "weekly", dt.date(2026, 10, 22)),
        (dt.date(2026, 6, 30), "semiannual", dt.date(2026, 12, 30)),
        (dt.date(2028, 2, 29), "yearly", dt.date(2029, 2, 28)),
    ],
)
def test_next_dates(date: dt.date, frequency: str, expected: dt.date) -> None:
    assert advance(date, frequency) == expected


def test_forecast_of_the_coming_weeks(ana: TestClient, account: str) -> None:
    new_item(
        ana,
        account,
        next_date="2026-10-27",
        name="Préstamo",
        kind="expense",
        amount="352.59",
        match_text="CUOTA PTMO",
    )
    new_item(ana, account, next_date="2026-11-01")

    upcoming = ana.get("/api/recurring/upcoming", params={"days": 45}).json()

    assert [(u["name"], u["date"], u["amount"]) for u in upcoming] == [
        ("Préstamo", "2026-10-27", "-352.59"),
        ("Nómina", "2026-11-01", "1566.67"),
        ("Préstamo", "2026-11-27", "-352.59"),
    ]


def test_the_real_movement_fulfils_it(ana: TestClient, account: str) -> None:
    item = new_item(ana, account)

    add(ana, account, "income", "1566.67", date="2026-10-30", description="TRANSF NOMI /EMPRESA")
    not_it = add(ana, account, "income", "1566.67", date="2026-10-30", description="Otra cosa")

    updated = ana.get("/api/recurring").json()[0]
    assert updated["next_date"] == "2026-12-01"
    assert updated["last_transaction_id"] != not_it["id"]
    assert updated["id"] == item["id"]


def test_amounts_within_the_tolerance_count(ana: TestClient, account: str) -> None:
    new_item(ana, account, kind="expense", amount="60", match_text="IBERDROLA", tolerance="10")

    add(ana, account, "expense", "70", date="2026-11-01", description="RECIBO IBERDROLA")
    assert ana.get("/api/recurring").json()[0]["next_date"] == "2026-11-01"  # 16 % off

    add(ana, account, "expense", "64.50", date="2026-11-02", description="RECIBO IBERDROLA")
    assert ana.get("/api/recurring").json()[0]["next_date"] == "2026-12-01"


def test_overdue_items_reach_the_review_tray(
    ana: TestClient, account: str, fake_clock: FakeClock
) -> None:
    new_item(ana, account, next_date="2026-10-16")
    assert ana.get("/api/inbox").json()["overdue"] == []

    fake_clock.advance(days=5)  # 20/10: four days late
    overdue = ana.get("/api/inbox").json()["overdue"]
    assert [(o["name"], o["date"], o["overdue"]) for o in overdue] == [
        ("Nómina", "2026-10-16", True)
    ]


def test_edit_and_delete(ana: TestClient, account: str) -> None:
    item = new_item(ana, account)
    body = {**item, "amount": "1600"}
    del body["id"], body["last_transaction_id"]

    assert ana.put(f"/api/recurring/{item['id']}", json=body).json()["amount"] == "1600.00"
    assert ana.delete(f"/api/recurring/{item['id']}").status_code == 204
    assert ana.get("/api/recurring").json() == []


@pytest.mark.parametrize(
    ("fields", "message"),
    [({"amount": "0"}, "mayor que cero"), ({"tolerance": "80"}, "de 0 % a 50 %")],
)
def test_validation(ana: TestClient, account: str, fields: dict[str, str], message: str) -> None:
    body = {
        "name": "X",
        "account_id": account,
        "kind": "expense",
        "amount": "10",
        "match_text": "XX",
        "next_date": "2026-11-01",
        **fields,
    }
    response = ana.post("/api/recurring", json=body)

    assert response.status_code == 422
    assert message in response.json()["error"]["message"]


def test_recurring_items_are_private(ana: TestClient, bea: TestClient, account: str) -> None:
    item = new_item(ana, account)

    assert bea.get("/api/recurring").json() == []
    assert bea.delete(f"/api/recurring/{item['id']}").status_code == 404

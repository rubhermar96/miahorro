"""Savings goals (RF-OBJ-01, 02, 03) and the savings rate (RF-OBJ-06)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import FakeClock
from tests.test_accounts import new_account
from tests.test_transactions import add, transfer


@pytest.fixture
def account(ana: TestClient) -> str:
    return str(new_account(ana, opening_date="2026-01-01", opening_balance="5000")["id"])


def new_goal(client: TestClient, **fields: Any) -> Any:
    body = {"name": "Entrada del piso", "target_amount": "12000", **fields}
    response = client.post("/api/goals", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def put_aside(client: TestClient, goal: Any, account: str, amount: str, **fields: Any) -> Any:
    return client.post(
        f"/api/goals/{goal['id']}/contributions",
        json={"account_id": account, "amount": amount, **fields},
    )


def accounts_by_id(client: TestClient) -> dict[str, Any]:
    return {a["id"]: a for a in client.get("/api/accounts").json()}


def test_a_goal_with_a_date_says_how_much_a_month(ana: TestClient) -> None:
    goal = new_goal(ana, target_date="2027-09-30", priority=1, icon="🏠")

    assert (goal["saved"], goal["remaining"], goal["percent"]) == ("0.00", "12000.00", 0)
    # 12 monthly contributions (October 2026 to September 2027).
    assert goal["required_monthly"] == "1000.00"
    assert (goal["status"], goal["pace"], goal["estimated_date"]) == ("starting", None, None)


def test_money_set_aside_is_reserved_in_its_account(ana: TestClient, account: str) -> None:
    goal = new_goal(ana)

    response = put_aside(ana, goal, account, "3000")

    assert response.status_code == 201, response.text
    assert (response.json()["saved"], response.json()["percent"]) == ("3000.00", 25)
    shown = accounts_by_id(ana)[account]
    assert (shown["balance"], shown["reserved"], shown["available"]) == (
        "5000.00",
        "3000.00",
        "2000.00",
    )


def test_cannot_set_aside_more_than_is_available(ana: TestClient, account: str) -> None:
    house, car = new_goal(ana), new_goal(ana, name="Coche")
    put_aside(ana, house, account, "4000")

    response = put_aside(ana, car, account, "1500")

    assert response.status_code == 409
    assert response.json()["error"]["message"] == (
        "En «Nómina» solo hay 1.000,00 € disponibles para apartar."
    )


def test_take_money_back(ana: TestClient, account: str, fake_clock: FakeClock) -> None:
    goal = new_goal(ana)
    put_aside(ana, goal, account, "1000")
    fake_clock.advance(minutes=1)

    assert put_aside(ana, goal, account, "1500", action="withdraw").status_code == 409
    back = put_aside(ana, goal, account, "400", action="withdraw").json()

    assert back["saved"] == "600.00"
    assert [c["amount"] for c in ana.get(f"/api/goals/{goal['id']}/contributions").json()] == [
        "-400.00",
        "1000.00",
    ]


def test_a_whole_account_counts_entirely(ana: TestClient, account: str) -> None:
    savings = str(new_account(ana, name="Ahorro piso", opening_balance="7000")["id"])

    goal = new_goal(ana, account_ids=[savings])
    add(ana, savings, "income", "500", date="2026-10-10")

    assert ana.get(f"/api/goals/{goal['id']}").json()["saved"] == "7500.00"
    shown = accounts_by_id(ana)[savings]
    assert (shown["reserved"], shown["available"]) == ("7500.00", "0.00")
    # Its money is the goal's: no piggy bank can take from it.
    assert put_aside(ana, new_goal(ana, name="Otro"), savings, "1").status_code == 409


def test_an_account_is_whole_for_one_goal_only(ana: TestClient) -> None:
    savings = str(new_account(ana, name="Ahorro", opening_balance="100")["id"])
    new_goal(ana, account_ids=[savings])

    response = ana.post(
        "/api/goals", json={"name": "Otro", "target_amount": "10", "account_ids": [savings]}
    )

    assert response.status_code == 409


def test_pace_and_estimated_date(ana: TestClient, account: str, fake_clock: FakeClock) -> None:
    goal = new_goal(ana, target_amount="3000", target_date="2027-12-31")
    put_aside(ana, goal, account, "1000")  # starting point, not pace

    # Sessions expire after 30 idle days: the clock moves in steps, using the app meanwhile.
    fake_clock.advance(days=20)
    ana.get("/api/goals").raise_for_status()
    fake_clock.advance(days=20)
    put_aside(ana, goal, account, "200")
    fake_clock.advance(days=21)  # two months since the start
    put_aside(ana, goal, account, "200")

    state = ana.get(f"/api/goals/{goal['id']}").json()
    assert state["saved"] == "1400.00"
    assert state["pace"] == "199.59"  # 400 € in 61 days
    assert state["estimated_date"] == "2027-08-17"  # 1.600 € more at that pace
    assert state["status"] == "on_track"  # 1.600 € in 13 months needs 123,08 € a month


def test_behind_when_the_pace_is_not_enough(
    ana: TestClient, account: str, fake_clock: FakeClock
) -> None:
    goal = new_goal(ana, target_amount="3000", target_date="2027-01-31")
    put_aside(ana, goal, account, "100")
    fake_clock.advance(days=20)
    ana.get("/api/goals").raise_for_status()
    fake_clock.advance(days=15)
    put_aside(ana, goal, account, "100")

    assert ana.get(f"/api/goals/{goal['id']}").json()["status"] == "behind"


def test_achieved_goals_go_last(ana: TestClient) -> None:
    done = new_goal(ana, name="Viaje", priority=1)
    new_goal(ana, name="Coche", priority=3)
    new_goal(ana, name="Piso", priority=1)

    ana.patch(f"/api/goals/{done['id']}", json={"achieved": True}).raise_for_status()

    goals = ana.get("/api/goals").json()
    assert [(g["name"], g["status"]) for g in goals] == [
        ("Piso", "no_date"),
        ("Coche", "no_date"),
        ("Viaje", "achieved"),
    ]


def test_deleting_a_goal_releases_its_money(ana: TestClient, account: str) -> None:
    goal = new_goal(ana)
    put_aside(ana, goal, account, "2000")

    assert ana.delete(f"/api/goals/{goal['id']}").status_code == 204

    assert accounts_by_id(ana)[account]["available"] == "5000.00"


def test_edit_a_goal(ana: TestClient) -> None:
    goal = new_goal(ana, target_date="2027-01-01")

    edited = ana.patch(
        f"/api/goals/{goal['id']}", json={"name": "Piso", "target_date": None}
    ).json()

    assert (edited["name"], edited["target_date"], edited["status"]) == ("Piso", None, "no_date")


@pytest.mark.parametrize(
    ("fields", "message"),
    [({"target_amount": "0"}, "mayor que cero"), ({"name": "  "}, "nombre")],
)
def test_validation(ana: TestClient, fields: dict[str, str], message: str) -> None:
    response = ana.post("/api/goals", json={"name": "X", "target_amount": "1", **fields})

    assert response.status_code == 422
    assert message in response.json()["error"]["message"]


def test_goals_are_private(ana: TestClient, bea: TestClient, account: str) -> None:
    goal = new_goal(ana)

    assert bea.get("/api/goals").json() == []
    assert bea.get(f"/api/goals/{goal['id']}").status_code == 404
    bea_goal = new_goal(bea)
    # Nobody sets aside money in someone else's account.
    assert put_aside(bea, bea_goal, account, "1").status_code == 404


# --- Savings rate -----------------------------------------------------------------------------


def test_savings_rate_per_financial_month(ana: TestClient, account: str) -> None:
    ana.patch("/api/me/preferences", json={"month_start_day": 25, "savings_rate_target": 20})
    other = str(new_account(ana, name="Ahorro")["id"])
    add(ana, account, "income", "2000", date="2026-09-25")  # payday opens the month
    add(ana, account, "expense", "1500", date="2026-10-10")
    transfer(ana, account, other, "300")  # moving money is not spending it
    add(ana, account, "expense", "100", date="2026-09-24")  # previous financial month

    rate = ana.get("/api/savings-rate", params={"months": 2}).json()

    assert rate["target"] == 20
    assert rate["periods"] == [
        {
            "start": "2026-08-25",
            "end": "2026-09-24",
            "income": "0.00",
            "expenses": "-100.00",
            "saved": "-100.00",
            "rate": None,
        },
        {
            "start": "2026-09-25",
            "end": "2026-10-15",  # today
            "income": "2000.00",
            "expenses": "-1500.00",
            "saved": "500.00",
            "rate": "25.0",
        },
    ]


def test_the_savings_target_can_be_removed(ana: TestClient) -> None:
    ana.patch("/api/me/preferences", json={"savings_rate_target": 25})

    me = ana.patch("/api/me/preferences", json={"savings_rate_target": None}).json()

    assert me["preferences"]["savings_rate_target"] is None

"""Budgets: limits and zero-based, by financial month (RF-PRS-01…04)."""

from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import FakeClock
from tests.test_accounts import new_account
from tests.test_transactions import add, category_id, transfer

# Today is 15/10/2026 (fake clock); with months from day 1, October is the current month.


@pytest.fixture
def account(ana: TestClient) -> str:
    return str(new_account(ana, opening_date="2026-01-01", opening_balance="3000")["id"])


def mode(client: TestClient, value: str, **fields: Any) -> None:
    client.patch("/api/me/preferences", json={"budget_mode": value, **fields}).raise_for_status()


def put(client: TestClient, category: str, amount: str, date: str | None = None) -> Any:
    response = client.put(
        f"/api/budget/lines/{category_id(client, category)}",
        json={"amount": amount, "date": date},
    )
    assert response.status_code == 200, response.text
    return response.json()


def budget(client: TestClient, date: str | None = None) -> Any:
    params = {"date": date} if date else {}
    return client.get("/api/budget", params=params).json()


def line(client: TestClient, state: Any, category: str) -> tuple[str, str, str, str]:
    wanted = category_id(client, category)
    found = next(li for li in state["lines"] if li["category_id"] == wanted)
    return (found["assigned"], found["activity"], found["carried"], found["available"])


def test_no_mode_until_chosen(ana: TestClient) -> None:
    state = budget(ana)

    assert (state["mode"], state["lines"]) == (None, [])
    response = ana.put(f"/api/budget/lines/{category_id(ana, 'Ocio')}", json={"amount": "100"})
    assert response.status_code == 409


# --- Limits -----------------------------------------------------------------------------------


def test_limits_show_spending_against_the_cap(ana: TestClient, account: str) -> None:
    mode(ana, "limits")
    put(ana, "Alimentación", "400")
    add(
        ana,
        account,
        "expense",
        "120",
        date="2026-10-03",
        category_id=category_id(ana, "Supermercado"),
    )
    add(
        ana,
        account,
        "expense",
        "30",
        date="2026-10-05",
        category_id=category_id(ana, "Restaurantes"),
    )
    add(ana, account, "expense", "50", date="2026-10-06", category_id=category_id(ana, "Ocio"))
    add(
        ana,
        account,
        "expense",
        "9",
        date="2026-09-30",
        category_id=category_id(ana, "Restaurantes"),
    )

    state = budget(ana)

    # Subcategories count in their main category; September is another month.
    assert line(ana, state, "Alimentación") == ("400.00", "-150.00", "0.00", "250.00")
    assert state["unbudgeted"] == "-50.00"
    assert (state["start"], state["end"]) == ("2026-10-01", "2026-10-31")
    assert (state["cash"], state["to_assign"]) == (None, None)


def test_a_limit_holds_in_the_following_months(ana: TestClient) -> None:
    mode(ana, "limits")
    put(ana, "Ocio", "100", date="2026-08-10")
    put(ana, "Ocio", "150", date="2026-10-02")

    assert line(ana, budget(ana, "2026-09-20"), "Ocio")[0] == "100.00"
    assert line(ana, budget(ana, "2026-12-01"), "Ocio")[0] == "150.00"
    assert budget(ana, "2026-07-01")["lines"] == []  # before the first limit


def test_removing_a_limit_from_a_month_on(ana: TestClient) -> None:
    mode(ana, "limits")
    put(ana, "Ocio", "100", date="2026-09-01")

    ana.delete(f"/api/budget/lines/{category_id(ana, 'Ocio')}").raise_for_status()

    assert budget(ana)["lines"] == []
    assert len(budget(ana, "2026-09-15")["lines"]) == 1  # September keeps it


def test_a_subcategory_with_its_own_line_is_not_counted_twice(
    ana: TestClient, account: str
) -> None:
    mode(ana, "limits")
    put(ana, "Alimentación", "400")
    put(ana, "Restaurantes", "100")
    add(
        ana,
        account,
        "expense",
        "120",
        date="2026-10-03",
        category_id=category_id(ana, "Supermercado"),
    )
    add(
        ana,
        account,
        "expense",
        "30",
        date="2026-10-05",
        category_id=category_id(ana, "Restaurantes"),
    )

    state = budget(ana)

    assert line(ana, state, "Alimentación")[1] == "-120.00"
    assert line(ana, state, "Restaurantes")[1] == "-30.00"


def test_optional_rollover_in_limits(ana: TestClient, account: str) -> None:
    mode(ana, "limits")
    put(ana, "Ocio", "100", date="2026-09-01")
    add(ana, account, "expense", "70", date="2026-09-10", category_id=category_id(ana, "Ocio"))

    assert line(ana, budget(ana), "Ocio")[2:] == ("0.00", "100.00")

    mode(ana, "limits", budget_rollover=True)
    assert line(ana, budget(ana), "Ocio")[2:] == ("30.00", "130.00")


# --- Zero-based -------------------------------------------------------------------------------


def test_assigned_plus_to_assign_is_the_cash(ana: TestClient, account: str) -> None:
    mode(ana, "zero_based")
    savings = str(new_account(ana, name="Ahorro", kind="savings", opening_balance="1000")["id"])
    new_account(ana, name="Depósito", kind="deposit", opening_balance="9000")  # not everyday
    put(ana, "Alimentación", "400")
    put(ana, "Ocio", "100")
    add(ana, account, "expense", "50", date="2026-10-06", category_id=category_id(ana, "Ocio"))
    add(ana, account, "income", "2000", date="2026-10-01", category_id=category_id(ana, "Nómina"))
    transfer(ana, account, savings, "300")

    state = budget(ana)

    assert state["cash"] == "5950.00"  # 3000 + 1000 + 2000 - 50
    assert state["available"] == "450.00"
    assert state["to_assign"] == "5500.00"
    assert Decimal(state["to_assign"]) + Decimal(state["available"]) == Decimal(state["cash"])


def test_goals_money_is_not_to_assign(ana: TestClient, account: str) -> None:
    mode(ana, "zero_based")
    goal = ana.post("/api/goals", json={"name": "Piso", "target_amount": "10000"}).json()
    ana.post(
        f"/api/goals/{goal['id']}/contributions", json={"account_id": account, "amount": "1000"}
    ).raise_for_status()

    assert budget(ana)["to_assign"] == "2000.00"


def test_zero_based_carries_leftovers_and_overspending(ana: TestClient, account: str) -> None:
    mode(ana, "zero_based")
    put(ana, "Ocio", "100", date="2026-08-05")
    put(ana, "Alimentación", "300", date="2026-08-05")
    add(ana, account, "expense", "60", date="2026-08-20", category_id=category_id(ana, "Ocio"))
    add(
        ana,
        account,
        "expense",
        "350",
        date="2026-08-21",
        category_id=category_id(ana, "Supermercado"),
    )
    put(ana, "Alimentación", "300", date="2026-09-05")

    september = budget(ana, "2026-09-10")

    assert line(ana, september, "Ocio") == ("0.00", "0.00", "40.00", "40.00")
    assert line(ana, september, "Alimentación") == ("300.00", "0.00", "-50.00", "250.00")
    # Money is kept from month to month: the line totals plus "to assign" are the cash.
    for date in ("2026-08-10", "2026-09-10", "2026-10-10"):
        state = budget(ana, date)
        assert Decimal(state["to_assign"]) + Decimal(state["available"]) == Decimal(state["cash"])


def test_move_money_between_categories(ana: TestClient) -> None:
    mode(ana, "zero_based")
    put(ana, "Ocio", "100")

    response = ana.post(
        "/api/budget/move",
        json={
            "from_category_id": category_id(ana, "Ocio"),
            "to_category_id": category_id(ana, "Restaurantes"),
            "amount": "40",
        },
    )

    assert response.status_code == 200, response.text
    state = response.json()
    assert line(ana, state, "Ocio")[3] == "60.00"
    assert line(ana, state, "Restaurantes")[3] == "40.00"
    too_much = ana.post(
        "/api/budget/move",
        json={
            "from_category_id": category_id(ana, "Ocio"),
            "to_category_id": category_id(ana, "Restaurantes"),
            "amount": "61",
        },
    )
    assert too_much.status_code == 409


def test_move_money_that_came_from_last_month(ana: TestClient) -> None:
    mode(ana, "zero_based")
    put(ana, "Ocio", "100", date="2026-09-05")

    ana.post(
        "/api/budget/move",
        json={
            "from_category_id": category_id(ana, "Ocio"),
            "to_category_id": category_id(ana, "Viajes"),
            "amount": "100",
        },
    ).raise_for_status()

    state = budget(ana)
    assert line(ana, state, "Ocio") == ("-100.00", "0.00", "100.00", "0.00")
    assert line(ana, state, "Viajes")[3] == "100.00"


def test_copy_last_months_assignments(ana: TestClient) -> None:
    mode(ana, "zero_based")
    put(ana, "Ocio", "100", date="2026-09-05")
    put(ana, "Alimentación", "300", date="2026-09-05")
    put(ana, "Ocio", "80")  # already set this month: kept

    state = ana.post("/api/budget/copy-previous", json={}).json()

    assert line(ana, state, "Ocio")[0] == "80.00"
    assert line(ana, state, "Alimentación")[0] == "300.00"


def test_only_an_empty_line_can_be_removed(ana: TestClient) -> None:
    mode(ana, "zero_based")
    put(ana, "Ocio", "100")
    ocio = category_id(ana, "Ocio")

    assert ana.delete(f"/api/budget/lines/{ocio}").status_code == 409
    put(ana, "Ocio", "0")
    assert ana.delete(f"/api/budget/lines/{ocio}").status_code == 200
    assert budget(ana)["lines"] == []


# --- Both modes -------------------------------------------------------------------------------


def test_changing_mode_keeps_the_data(ana: TestClient) -> None:
    mode(ana, "limits")
    put(ana, "Ocio", "100")
    mode(ana, "zero_based")
    put(ana, "Ocio", "150")

    mode(ana, "limits")

    assert line(ana, budget(ana), "Ocio")[0] == "150.00"


def test_months_start_on_payday(ana: TestClient, account: str, fake_clock: FakeClock) -> None:
    ana.patch("/api/me/preferences", json={"month_start_day": 25})
    mode(ana, "limits")
    put(ana, "Ocio", "100")
    add(ana, account, "expense", "10", date="2026-09-25", category_id=category_id(ana, "Ocio"))
    add(ana, account, "expense", "20", date="2026-10-24", category_id=category_id(ana, "Ocio"))
    add(ana, account, "expense", "40", date="2026-10-25", category_id=category_id(ana, "Ocio"))

    state = budget(ana)

    assert (state["start"], state["end"]) == ("2026-09-25", "2026-10-24")
    assert (state["previous_start"], state["next_start"]) == ("2026-08-25", "2026-10-25")
    assert line(ana, state, "Ocio")[1] == "-30.00"
    assert line(ana, budget(ana, "2026-10-25"), "Ocio")[1] == "-40.00"


def test_only_expense_categories_are_budgeted(ana: TestClient) -> None:
    mode(ana, "zero_based")

    response = ana.put(f"/api/budget/lines/{category_id(ana, 'Nómina')}", json={"amount": "100"})

    assert response.status_code == 422


def test_budgets_are_private(ana: TestClient, bea: TestClient) -> None:
    mode(ana, "limits")
    mode(bea, "limits")
    put(ana, "Ocio", "100")

    assert budget(bea)["lines"] == []
    response = bea.put(f"/api/budget/lines/{category_id(ana, 'Ocio')}", json={"amount": "100"})
    assert response.status_code == 404

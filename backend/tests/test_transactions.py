"""Income, expenses, transfers and search (RF-MOV-01, 03, 04, 15)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.test_accounts import new_account


def category_id(client: TestClient, name: str) -> str:
    return str(next(c["id"] for c in client.get("/api/categories").json() if c["name"] == name))


def add(client: TestClient, account_id: str, kind: str, amount: str, **fields: Any) -> Any:
    body = {
        "account_id": account_id,
        "date": "2026-10-10",
        "kind": kind,
        "amount": amount,
        **fields,
    }
    response = client.post("/api/transactions", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def balance(client: TestClient, account_id: str) -> str:
    return str(client.get(f"/api/accounts/{account_id}").json()["balance"])


@pytest.fixture
def account(ana: TestClient) -> str:
    return str(new_account(ana, opening_balance="1000")["id"])


def test_expenses_and_income_carry_their_sign(ana: TestClient, account: str) -> None:
    expense = add(ana, account, "expense", "45.20", description="Mercadona")
    income = add(ana, account, "income", "-2000", description="Nómina")  # sign comes from kind

    assert (expense["amount"], income["amount"]) == ("-45.20", "2000.00")
    assert balance(ana, account) == "2954.80"


def test_quick_entry_needs_only_amount_account_and_kind(ana: TestClient, account: str) -> None:
    row = add(ana, account, "expense", "3.5")

    assert (row["description"], row["category_id"], row["tags"], row["note"]) == (
        "",
        None,
        [],
        None,
    )
    assert row["source"] == "manual"


def test_zero_is_not_an_amount(ana: TestClient, account: str) -> None:
    response = ana.post(
        "/api/transactions",
        json={"account_id": account, "date": "2026-10-10", "kind": "expense", "amount": "0"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["message"] == "El importe no puede ser cero."


def test_category_must_match_the_kind(ana: TestClient, account: str) -> None:
    salary = category_id(ana, "Nómina")

    response = ana.post(
        "/api/transactions",
        json={
            "account_id": account,
            "date": "2026-10-10",
            "kind": "expense",
            "amount": "10",
            "category_id": salary,
        },
    )

    assert response.status_code == 422


def test_tags_are_normalised_and_suggested(ana: TestClient, account: str) -> None:
    add(ana, account, "expense", "100", tags=["#Viaje-Japón", " viaje-japón ", "hotel"])
    add(ana, account, "expense", "30", tags=["viaje-japón"])

    row = ana.get("/api/transactions").json()["items"][-1]

    assert row["tags"] == ["viaje-japón", "hotel"]
    assert ana.get("/api/tags").json() == [
        {"tag": "viaje-japón", "count": 2},
        {"tag": "hotel", "count": 1},
    ]


def test_edit_changes_sign_when_the_kind_changes(ana: TestClient, account: str) -> None:
    row = add(ana, account, "expense", "50")

    edited = ana.patch(f"/api/transactions/{row['id']}", json={"kind": "income"}).json()
    resized = ana.patch(f"/api/transactions/{row['id']}", json={"amount": "75.25"}).json()

    assert edited["amount"] == "50.00"
    assert resized["amount"] == "75.25"
    assert balance(ana, account) == "1075.25"


def test_delete_a_transaction(ana: TestClient, account: str) -> None:
    row = add(ana, account, "expense", "50")

    assert ana.delete(f"/api/transactions/{row['id']}").status_code == 204
    assert balance(ana, account) == "1000.00"


# --- Transfers ------------------------------------------------------------------------------


@pytest.fixture
def savings(ana: TestClient) -> str:
    return str(new_account(ana, name="Ahorro", kind="savings")["id"])


def transfer(client: TestClient, source: str, target: str, amount: str, **fields: Any) -> Any:
    body = {
        "from_account_id": source,
        "to_account_id": target,
        "date": "2026-10-11",
        "amount": amount,
        **fields,
    }
    return client.post("/api/transfers", json=body)


def test_transfer_moves_money_without_counting_as_income_or_expense(
    ana: TestClient, account: str, savings: str
) -> None:
    response = transfer(ana, account, savings, "300")

    assert response.status_code == 201
    out_leg, in_leg = response.json()
    assert (out_leg["amount"], in_leg["amount"]) == ("-300.00", "300.00")
    assert out_leg["transfer_id"] == in_leg["transfer_id"]
    assert out_leg["description"] == "Transferencia a Ahorro"
    assert in_leg["description"] == "Transferencia desde Nómina"
    assert (balance(ana, account), balance(ana, savings)) == ("700.00", "300.00")
    page = ana.get("/api/transactions").json()
    assert (page["income"], page["expenses"]) == ("0.00", "0.00")


def test_editing_one_leg_updates_the_whole_transfer(
    ana: TestClient, account: str, savings: str
) -> None:
    out_leg, _ = transfer(ana, account, savings, "300").json()

    ana.patch(f"/api/transactions/{out_leg['id']}", json={"amount": "250", "date": "2026-10-12"})

    assert (balance(ana, account), balance(ana, savings)) == ("750.00", "250.00")
    dates = {row["date"] for row in ana.get("/api/transactions").json()["items"]}
    assert dates == {"2026-10-12"}
    blocked = ana.patch(f"/api/transactions/{out_leg['id']}", json={"kind": "expense"})
    assert blocked.status_code == 422


def test_deleting_one_leg_deletes_the_transfer(ana: TestClient, account: str, savings: str) -> None:
    _, in_leg = transfer(ana, account, savings, "300").json()

    ana.delete(f"/api/transactions/{in_leg['id']}")

    assert ana.get("/api/transactions").json()["total"] == 0


@pytest.mark.parametrize(("amount", "same_account"), [("0", False), ("-5", False), ("5", True)])
def test_invalid_transfers(
    ana: TestClient, account: str, savings: str, amount: str, same_account: bool
) -> None:
    response = transfer(ana, account, account if same_account else savings, amount)

    assert response.status_code == 422


def test_transfers_need_the_same_currency(ana: TestClient, account: str) -> None:
    dollars = new_account(ana, name="USD", currency="USD")["id"]

    assert transfer(ana, account, dollars, "10").status_code == 422


# --- Search and totals ----------------------------------------------------------------------


@pytest.fixture
def history(ana: TestClient, account: str, savings: str) -> dict[str, str]:
    food = category_id(ana, "Alimentación")
    groceries = category_id(ana, "Supermercado")
    salary = category_id(ana, "Nómina")
    add(ana, account, "income", "2000", date="2026-09-30", description="Nómina", category_id=salary)
    add(
        ana,
        account,
        "expense",
        "60",
        date="2026-10-02",
        description="Mercadona",
        category_id=groceries,
    )
    add(ana, account, "expense", "25", date="2026-10-05", description="Pizzería", category_id=food)
    add(
        ana,
        account,
        "expense",
        "12",
        date="2026-10-08",
        description="Cine",
        note="con Bea",
        tags=["ocio"],
    )
    transfer(ana, account, savings, "500", date="2026-10-09")
    return {"food": food, "groceries": groceries}


def descriptions(page: dict[str, Any]) -> list[str]:
    return [row["description"] for row in page["items"]]


def test_list_is_newest_first_with_totals(ana: TestClient, history: dict[str, str]) -> None:
    page = ana.get("/api/transactions").json()

    assert page["total"] == 6
    assert descriptions(page)[:3] == [
        "Transferencia a Ahorro",
        "Transferencia desde Nómina",
        "Cine",
    ]
    assert (page["income"], page["expenses"]) == ("2000.00", "-97.00")


def test_filter_by_main_category_includes_subcategories(
    ana: TestClient, history: dict[str, str]
) -> None:
    page = ana.get(f"/api/transactions?category_id={history['food']}").json()

    assert descriptions(page) == ["Pizzería", "Mercadona"]
    assert page["expenses"] == "-85.00"


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("q=merca", ["Mercadona"]),
        ("q=bea", ["Cine"]),  # the note is searched too
        ("tag=%23Ocio", ["Cine"]),
        ("kind=income", ["Nómina"]),
        ("date_from=2026-10-01&date_to=2026-10-05", ["Pizzería", "Mercadona"]),
    ],
)
def test_filters(ana: TestClient, history: dict[str, str], query: str, expected: list[str]) -> None:
    assert descriptions(ana.get(f"/api/transactions?{query}").json()) == expected


def test_pages(ana: TestClient, history: dict[str, str]) -> None:
    first = ana.get("/api/transactions?limit=4").json()
    second = ana.get("/api/transactions?limit=4&offset=4").json()

    assert (len(first["items"]), len(second["items"]), first["total"]) == (4, 2, 6)
    assert descriptions(second) == ["Mercadona", "Nómina"]


def test_filter_by_account(ana: TestClient, history: dict[str, str], savings: str) -> None:
    page = ana.get(f"/api/transactions?account_id={savings}").json()

    assert descriptions(page) == ["Transferencia desde Nómina"]


# --- Isolation (RF-PLT-01) ------------------------------------------------------------------


def test_nobody_reaches_another_users_transactions(
    ana: TestClient, bea: TestClient, account: str
) -> None:
    row = add(ana, account, "expense", "9.99", tags=["privado"])
    url = f"/api/transactions/{row['id']}"
    bea_account = new_account(bea)["id"]

    assert bea.get("/api/transactions").json()["total"] == 0
    assert bea.get("/api/tags").json() == []
    assert bea.get(url).status_code == 404
    assert bea.patch(url, json={"amount": "1"}).status_code == 404
    assert bea.delete(url).status_code == 404
    assert transfer(bea, bea_account, account, "10").status_code == 404
    assert transfer(bea, account, bea_account, "10").status_code == 404
    ana_category = category_id(ana, "Supermercado")
    response = bea.post(
        "/api/transactions",
        json={
            "account_id": bea_account,
            "date": "2026-10-10",
            "kind": "expense",
            "amount": "1",
            "category_id": ana_category,
        },
    )
    assert response.status_code == 404
    assert ana.get(url).json()["amount"] == "-9.99"


def test_movements_before_the_opening_date_do_not_change_the_balance(ana: TestClient) -> None:
    account = str(new_account(ana, opening_date="2026-10-10", opening_balance="100")["id"])
    add(ana, account, "expense", "30", date="2026-10-09")  # already inside the 100
    add(ana, account, "expense", "5", date="2026-10-10")  # from the opening date on, it counts

    assert balance(ana, account) == "95.00"


def test_each_movement_shows_the_balance_right_after_it(ana: TestClient) -> None:
    account = str(new_account(ana, opening_date="2026-10-10", opening_balance="100")["id"])
    other = str(new_account(ana, name="Otra", opening_balance="0")["id"])
    add(ana, account, "expense", "30", date="2026-10-01", description="historial")
    add(ana, account, "income", "50", date="2026-10-11", description="cobro")
    add(ana, account, "expense", "5", date="2026-10-11", description="cafe")
    transfer(ana, account, other, "20", date="2026-10-12")
    add(ana, other, "expense", "1", date="2026-10-13", description="en la otra")

    def balances(**filters: str) -> list[tuple[str, str]]:
        items = ana.get("/api/transactions", params=filters).json()["items"]
        return [(item["description"], item["balance_after"]) for item in items]

    assert balances(account_id=account) == [
        ("Transferencia a Otra", "125.00"),
        ("cafe", "145.00"),  # same day: the later one first
        ("cobro", "150.00"),
        ("historial", "100.00"),  # before the anchor: the opening balance already had it
    ]
    # Filters do not change the balances: they come from the whole account.
    assert balances(account_id=account, q="cobro") == [("cobro", "150.00")]
    assert ("en la otra", "19.00") in balances()

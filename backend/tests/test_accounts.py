"""Accounts, remuneration history and reconciliation (RF-CTA-01…04, 07, 08)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient


def new_account(client: TestClient, **fields: Any) -> Any:
    body = {"name": "Nómina", "kind": "checking", "opening_date": "2026-01-01", **fields}
    response = client.post("/api/accounts", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def spend(client: TestClient, account_id: str, amount: str, **fields: Any) -> Any:
    body = {
        "account_id": account_id,
        "date": "2026-10-01",
        "kind": "expense",
        "amount": amount,
        **fields,
    }
    response = client.post("/api/transactions", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_an_account_with_an_opening_balance(ana: TestClient) -> None:
    account = new_account(
        ana,
        name="  Nómina ",
        institution="Bankinter",
        iban_last4="1234",
        opening_balance="1500.5",
    )

    assert account["name"] == "Nómina"
    assert account["currency"] == "EUR"
    assert account["opening_balance"] == "1500.50"
    assert account["balance"] == "1500.50"
    assert account["archived"] is False
    assert account["current_rate"] is None


def test_balance_is_opening_balance_plus_transactions(ana: TestClient) -> None:
    account = new_account(ana, opening_balance="100.00")
    spend(ana, account["id"], "0.10")
    spend(ana, account["id"], "0.20")

    assert ana.get(f"/api/accounts/{account['id']}").json()["balance"] == "99.70"


def test_accounts_are_listed_everyday_money_first(ana: TestClient) -> None:
    new_account(ana, name="Bitcoin", kind="crypto")
    new_account(ana, name="Depósito 12 meses", kind="deposit", maturity_date="2027-01-01")
    new_account(ana, name="Cartera", kind="cash")
    new_account(ana, name="Bankinter", kind="checking")

    names = [account["name"] for account in ana.get("/api/accounts").json()]

    assert names == ["Bankinter", "Depósito 12 meses", "Cartera", "Bitcoin"]


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"opening_balance": 12.5}, 'El importe se envía como texto, por ejemplo "12.50".'),
        ({"opening_balance": "12.505"}, "El importe tiene como mucho dos decimales."),
        ({"opening_balance": "12,50"}, "El importe no es válido."),
        (
            {"kind": "deposit", "maturity_date": "2025-12-31"},
            "El vencimiento debe ser posterior a la fecha de apertura.",
        ),
    ],
)
def test_invalid_accounts_are_explained(
    ana: TestClient, fields: dict[str, Any], message: str
) -> None:
    body = {"name": "X", "kind": "checking", "opening_date": "2026-01-01", **fields}

    response = ana.post("/api/accounts", json=body)

    assert response.status_code == 422
    assert response.json()["error"]["message"] == message


def test_only_the_last_four_iban_digits_are_kept(ana: TestClient) -> None:
    bad = ana.post(
        "/api/accounts",
        json={"name": "X", "kind": "checking", "opening_date": "2026-01-01", "iban_last4": "ES12"},
    )

    assert bad.status_code == 422


def test_fixed_term_deposit(ana: TestClient) -> None:
    deposit = new_account(
        ana,
        name="Depósito",
        kind="deposit",
        opening_balance="10000",
        opening_date="2026-04-01",
        maturity_date="2027-04-01",
        auto_renew=True,
        early_cancellation_note="Pierdes los intereses del último mes",
    )

    assert (deposit["maturity_date"], deposit["auto_renew"]) == ("2027-04-01", True)


def test_archived_accounts_are_hidden_but_kept(ana: TestClient) -> None:
    account = new_account(ana)
    spend(ana, account["id"], "10")

    archived = ana.patch(f"/api/accounts/{account['id']}", json={"archived": True}).json()

    assert archived["archived"] is True
    assert ana.get("/api/accounts").json() == []
    assert len(ana.get("/api/accounts?include_archived=true").json()) == 1
    response = ana.post(
        "/api/transactions",
        json={
            "account_id": account["id"],
            "date": "2026-10-02",
            "kind": "expense",
            "amount": "1",
        },
    )
    assert response.status_code == 409


def test_accounts_with_transactions_cannot_be_deleted(ana: TestClient) -> None:
    used = new_account(ana, name="Usada")
    spend(ana, used["id"], "5")
    empty = new_account(ana, name="Vacía")

    assert ana.delete(f"/api/accounts/{used['id']}").status_code == 409
    assert ana.delete(f"/api/accounts/{empty['id']}").status_code == 204


def test_edit_an_account(ana: TestClient) -> None:
    account = new_account(ana)

    edited = ana.patch(
        f"/api/accounts/{account['id']}",
        json={"name": "Cuenta nómina", "institution": "  ", "opening_balance": "50"},
    ).json()

    assert (edited["name"], edited["institution"], edited["balance"]) == (
        "Cuenta nómina",
        None,
        "50.00",
    )


# --- Remuneration ---------------------------------------------------------------------------


def tiered_rate(valid_from: str = "2026-09-01", **fields: Any) -> dict[str, Any]:
    return {
        "valid_from": valid_from,
        "tiers": [{"up_to": "10000", "rate": "2"}, {"up_to": None, "rate": "0"}],
        "tae": "2.02",
        "liquidation": "monthly",
        **fields,
    }


def test_tiered_rate_in_force_today(ana: TestClient) -> None:
    account = new_account(ana, kind="savings")

    added = ana.post(f"/api/accounts/{account['id']}/rates", json=tiered_rate())
    current = ana.get(f"/api/accounts/{account['id']}").json()["current_rate"]

    assert added.status_code == 201
    assert current["tiers"] == [
        {"up_to": "10000.00", "rate": "2.0000"},
        {"up_to": None, "rate": "0.0000"},
    ]
    assert (current["tae"], current["withholding"]) == ("2.0200", "19.0000")


def test_rate_history_keeps_every_change(ana: TestClient) -> None:
    account = new_account(ana, kind="savings")
    url = f"/api/accounts/{account['id']}/rates"
    ana.post(url, json=tiered_rate("2026-01-01", tiers=[{"rate": "3"}]))
    ana.post(url, json=tiered_rate("2026-09-01", tiers=[{"rate": "2"}]))
    ana.post(url, json=tiered_rate("2026-12-01", tiers=[{"rate": "1.5"}]))  # announced

    history = ana.get(url).json()
    current = ana.get(f"/api/accounts/{account['id']}").json()["current_rate"]

    assert [rate["valid_from"] for rate in history] == ["2026-01-01", "2026-09-01", "2026-12-01"]
    assert current["tiers"][0]["rate"] == "2.0000"  # today is 15/10/2026
    assert ana.post(url, json=tiered_rate("2026-09-01")).status_code == 409


@pytest.mark.parametrize(
    "tiers",
    [
        [{"up_to": "10000", "rate": "2"}],  # last tier must be open-ended
        [{"up_to": None, "rate": "2"}, {"up_to": None, "rate": "0"}],
        [{"up_to": "20000", "rate": "1"}, {"up_to": "10000", "rate": "2"}, {"rate": "0"}],
        [{"rate": "120"}],
    ],
)
def test_invalid_tiers_are_rejected(ana: TestClient, tiers: list[dict[str, Any]]) -> None:
    account = new_account(ana, kind="savings")

    response = ana.post(f"/api/accounts/{account['id']}/rates", json=tiered_rate(tiers=tiers))

    assert response.status_code == 422


def test_delete_a_rate(ana: TestClient) -> None:
    account = new_account(ana, kind="savings")
    rate = ana.post(f"/api/accounts/{account['id']}/rates", json=tiered_rate()).json()

    assert ana.delete(f"/api/accounts/{account['id']}/rates/{rate['id']}").status_code == 204
    assert ana.get(f"/api/accounts/{account['id']}/rates").json() == []


# --- Reconciliation -------------------------------------------------------------------------


def test_reconcile_records_the_difference(ana: TestClient) -> None:
    account = new_account(ana, opening_balance="100.00")

    result = ana.post(f"/api/accounts/{account['id']}/reconcile", json={"balance": "95.50"}).json()

    assert result["balance"] == "95.50"
    adjustment = result["adjustment"]
    assert (adjustment["kind"], adjustment["amount"], adjustment["date"]) == (
        "adjustment",
        "-4.50",
        "2026-10-15",
    )
    assert ana.get(f"/api/accounts/{account['id']}").json()["balance"] == "95.50"


def test_reconcile_without_difference_changes_nothing(ana: TestClient) -> None:
    account = new_account(ana, opening_balance="100.00")

    result = ana.post(f"/api/accounts/{account['id']}/reconcile", json={"balance": "100"}).json()

    assert result["adjustment"] is None
    assert ana.get("/api/transactions").json()["total"] == 0


# --- Isolation (RF-PLT-01) ------------------------------------------------------------------


def test_nobody_reaches_another_users_accounts(ana: TestClient, bea: TestClient) -> None:
    account = new_account(ana)
    url = f"/api/accounts/{account['id']}"

    assert bea.get("/api/accounts").json() == []
    assert bea.get(url).status_code == 404
    assert bea.patch(url, json={"name": "mía"}).status_code == 404
    assert bea.delete(url).status_code == 404
    assert bea.post(f"{url}/rates", json=tiered_rate()).status_code == 404
    assert bea.post(f"{url}/reconcile", json={"balance": "0"}).status_code == 404
    response = bea.post(
        "/api/transactions",
        json={"account_id": account["id"], "date": "2026-10-01", "kind": "income", "amount": "1"},
    )
    assert response.status_code == 404
    assert ana.get(url).json()["name"] == "Nómina"

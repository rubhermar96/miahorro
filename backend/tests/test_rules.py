"""Categorisation rules (RF-MOV-07) and bulk edit (RF-MOV-15)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.rules import suggest_match_text
from tests.test_accounts import new_account
from tests.test_transactions import add, category_id, transfer


@pytest.fixture
def account(ana: TestClient) -> str:
    return str(new_account(ana, opening_balance="1000")["id"])


def new_rule(client: TestClient, match_text: str, category: str, **fields: Any) -> Any:
    body = {"match_text": match_text, "category_id": category_id(client, category), **fields}
    response = client.post("/api/rules", json=body)
    assert response.status_code == 201, response.text
    return response.json()["rule"]


def category_name(client: TestClient, transaction: Any) -> str | None:
    row = client.get(f"/api/transactions/{transaction['id']}").json()
    names = {c["id"]: c["name"] for c in client.get("/api/categories").json()}
    return names.get(row["category_id"])


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("COMPRA TARJ. 1234 MERCADONA VALENCIA", "MERCADONA"),
        ("RECIBO IBERDROLA CLIENTES S.A.U.", "IBERDROLA"),
        ("COMPRA APPLE PAY 28/09 AMAZON EU", "AMAZON"),
        ("BAR PEPE", "BAR PEPE"),
        ("TRANSFERENCIA A FAVOR DE JUAN", "JUAN"),
        ("12345", "12345"),
    ],
)
def test_suggests_the_meaningful_part_of_a_concept(description: str, expected: str) -> None:
    assert suggest_match_text(description) == expected


def test_a_rule_categorises_new_movements_without_category(ana: TestClient, account: str) -> None:
    new_rule(ana, "mercadona", "Supermercado")

    matched = add(ana, account, "expense", "12", description="COMPRA MERCADONA")
    chosen = add(
        ana,
        account,
        "expense",
        "12",
        description="Mercadona",
        category_id=category_id(ana, "Restaurantes"),
    )
    other = add(ana, account, "expense", "12", description="Zara")

    assert category_name(ana, matched) == "Supermercado"
    assert category_name(ana, chosen) == "Restaurantes"  # what the user picks wins
    assert category_name(ana, other) is None


def test_matching_ignores_case_accents_and_spacing(ana: TestClient, account: str) -> None:
    new_rule(ana, "nomina  empresa", "Nómina")

    row = add(ana, account, "income", "2000", description="NÓMINA EMPRESA SL")

    assert category_name(ana, row) == "Nómina"


def test_rules_only_apply_to_their_kind_account_and_amounts(ana: TestClient, account: str) -> None:
    other_account = str(new_account(ana, name="Ahorro")["id"])
    new_rule(ana, "amazon", "Otros gastos", account_id=other_account)
    new_rule(ana, "amazon", "Ropa y calzado", amount_min="20", amount_max="100")

    cheap = add(ana, account, "expense", "5", description="AMAZON")
    clothes = add(ana, account, "expense", "50", description="AMAZON")
    refund = add(ana, account, "income", "50", description="AMAZON")  # expense category
    elsewhere = add(ana, other_account, "expense", "5", description="AMAZON")

    assert [category_name(ana, row) for row in (cheap, clothes, refund, elsewhere)] == [
        None,
        "Ropa y calzado",
        None,
        "Otros gastos",
    ]


def test_the_first_matching_rule_wins_and_new_rules_go_first(ana: TestClient, account: str) -> None:
    general = new_rule(ana, "amazon", "Otros gastos")
    new_rule(ana, "amazon prime", "Suscripciones")

    assert [r["match_text"] for r in ana.get("/api/rules").json()] == ["amazon prime", "amazon"]
    prime = add(ana, account, "expense", "4.99", description="AMAZON PRIME ES")
    assert category_name(ana, prime) == "Suscripciones"

    ana.patch(f"/api/rules/{general['id']}", json={"position": 0}).raise_for_status()

    assert [r["match_text"] for r in ana.get("/api/rules").json()] == ["amazon", "amazon prime"]
    again = add(ana, account, "expense", "4.99", description="AMAZON PRIME ES")
    assert category_name(ana, again) == "Otros gastos"


def test_apply_to_existing_movements(ana: TestClient, account: str) -> None:
    old = add(ana, account, "expense", "30", description="REPSOL")
    wrong = add(
        ana,
        account,
        "expense",
        "40",
        description="REPSOL",
        category_id=category_id(ana, "Supermercado"),
    )

    created = ana.post(
        "/api/rules",
        json={
            "match_text": "repsol",
            "category_id": category_id(ana, "Combustible"),
            "apply_to_existing": True,
        },
    ).json()

    assert created["applied"] == 2
    assert category_name(ana, old) == category_name(ana, wrong) == "Combustible"


def test_apply_all_rules_to_uncategorised_movements(ana: TestClient, account: str) -> None:
    pending = add(ana, account, "expense", "30", description="REPSOL")
    kept = add(
        ana,
        account,
        "expense",
        "40",
        description="REPSOL",
        category_id=category_id(ana, "Supermercado"),
    )
    new_rule(ana, "repsol", "Combustible")

    assert ana.post("/api/rules/apply", json={}).json() == {"applied": 1}

    assert category_name(ana, pending) == "Combustible"
    assert category_name(ana, kept) == "Supermercado"


def test_suggestion_after_correcting_a_category(ana: TestClient, account: str) -> None:
    row = add(ana, account, "expense", "12", description="COMPRA TARJ. 9999 MERCADONA ALZIRA")
    add(ana, account, "expense", "8", description="MERCADONA VALENCIA")
    ana.patch(
        f"/api/transactions/{row['id']}", json={"category_id": category_id(ana, "Supermercado")}
    )

    suggestion = ana.get("/api/rules/suggestion", params={"transaction_id": row["id"]}).json()

    assert suggestion == {"match_text": "MERCADONA", "matches": 1}


def test_edit_and_delete_rules(ana: TestClient) -> None:
    rule = new_rule(ana, "luz", "Luz")

    updated = ana.patch(f"/api/rules/{rule['id']}", json={"match_text": "iberdrola"}).json()
    assert updated["match_text"] == "iberdrola"
    assert ana.delete(f"/api/rules/{rule['id']}").status_code == 204
    assert ana.get("/api/rules").json() == []


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"match_text": " a "}, "al menos dos letras"),
        ({"amount_min": "-1"}, "sin signo"),
        ({"amount_min": "10", "amount_max": "5"}, "no puede ser menor"),
    ],
)
def test_rule_validation(ana: TestClient, fields: dict[str, str], message: str) -> None:
    body = {"match_text": "luz", "category_id": category_id(ana, "Luz"), **fields}

    response = ana.post("/api/rules", json=body)

    assert response.status_code == 422
    assert message in response.json()["error"]["message"]


def test_rules_are_private(ana: TestClient, bea: TestClient) -> None:
    rule = new_rule(ana, "luz", "Luz")

    assert bea.get("/api/rules").json() == []
    assert bea.delete(f"/api/rules/{rule['id']}").status_code == 404
    # Nor can a rule point to someone else's category.
    response = bea.post(
        "/api/rules", json={"match_text": "luz", "category_id": category_id(ana, "Luz")}
    )
    assert response.status_code == 404


# --- Bulk edit --------------------------------------------------------------------------------


def bulk(client: TestClient, ids: list[str], action: str, **fields: Any) -> Any:
    return client.post("/api/transactions/bulk", json={"ids": ids, "action": action, **fields})


def test_recategorise_several_at_once(ana: TestClient, account: str) -> None:
    rows = [add(ana, account, "expense", str(n), description=f"Gasto {n}") for n in (1, 2)]
    move = transfer(ana, account, str(new_account(ana, name="Otra")["id"]), "5").json()

    response = bulk(
        ana,
        [r["id"] for r in rows] + [move[0]["id"]],
        "categorise",
        category_id=category_id(ana, "Ocio"),
    )

    assert response.json() == {"affected": 2}  # the transfer has no category
    assert {category_name(ana, row) for row in rows} == {"Ocio"}


def test_one_category_cannot_fit_income_and_expenses(ana: TestClient, account: str) -> None:
    rows = [add(ana, account, "expense", "1"), add(ana, account, "income", "1")]

    response = bulk(
        ana, [r["id"] for r in rows], "categorise", category_id=category_id(ana, "Ocio")
    )

    assert response.status_code == 422
    assert category_name(ana, rows[0]) is None  # nothing changed


def test_tag_and_untag_several(ana: TestClient, account: str) -> None:
    rows = [add(ana, account, "expense", "1", tags=["viaje"]), add(ana, account, "expense", "2")]
    ids = [r["id"] for r in rows]

    assert bulk(ana, ids, "tag", tag="#Viaje").json() == {"affected": 1}
    assert bulk(ana, ids, "untag", tag="viaje").json() == {"affected": 2}
    assert bulk(ana, ids, "tag", tag="  ").status_code == 422


def test_delete_several_including_both_legs_of_a_transfer(ana: TestClient, account: str) -> None:
    other = str(new_account(ana, name="Otra")["id"])
    row = add(ana, account, "expense", "1")
    move = transfer(ana, account, other, "5").json()

    assert bulk(ana, [row["id"], move[0]["id"]], "delete").json() == {"affected": 3}
    assert ana.get("/api/transactions").json()["total"] == 0


def test_bulk_edit_only_touches_own_movements(
    ana: TestClient, bea: TestClient, account: str
) -> None:
    row = add(ana, account, "expense", "1")

    assert bulk(bea, [row["id"]], "delete").status_code == 404
    assert ana.get("/api/transactions").json()["total"] == 1

"""Importing statements: preview, duplicates, templates and undo (RF-IMP-01)."""

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import FakeClock
from tests.importers.pdf_samples import bankinter_pdf
from tests.importers.samples import DEBIT_CREDIT_CSV, SEMICOLON_CSV, xlsx_statement
from tests.test_accounts import new_account
from tests.test_transactions import add, balance, category_id

CSV = "text/csv"


@pytest.fixture
def account(ana: TestClient) -> str:
    return str(new_account(ana, opening_date="2026-10-01", opening_balance="0")["id"])


def preview(client: TestClient, account: str, content: bytes, **form: str) -> Any:
    response = client.post(
        "/api/imports/preview",
        data={"account_id": account, **form},
        files={"file": ("extracto.csv", content, CSV)},
    )
    assert response.status_code == 200, response.text
    return response.json()


def do_import(
    client: TestClient,
    account: str,
    content: bytes,
    rows: list[int] | None = None,
    **form: str,
) -> Any:
    shown = preview(client, account, content)
    # By default, what the preview proposes for each row; with rows, import just those.
    decisions = (
        {str(number): "import" for number in rows}
        if rows is not None
        else {str(row["number"]): row["decisions"][0] for row in shown["rows"]}
    )
    response = client.post(
        "/api/imports",
        data={
            "account_id": account,
            "mapping": json.dumps(shown["mapping"]),
            "decisions": json.dumps(decisions),
            **form,
        },
        files={"file": ("extracto.csv", content, CSV)},
    )
    assert response.status_code == 201, response.text
    return response.json()


def movements(client: TestClient, account: str) -> list[tuple[str, str, str, str | None]]:
    items = client.get("/api/transactions", params={"account_id": account}).json()["items"]
    return [(t["date"], t["description"], t["amount"], t["category_id"]) for t in items]


def test_preview_detects_columns_and_stores_nothing(ana: TestClient, account: str) -> None:
    shown = preview(ana, account, SEMICOLON_CSV)

    assert shown["columns"] == ["Fecha operación", "Fecha valor", "Concepto", "Importe", "Saldo"]
    assert shown["mapping"]["date"] == "Fecha operación"
    assert shown["mapping"]["decimal_comma"] is True
    assert [(r["number"], r["amount"], r["status"]) for r in shown["rows"]] == [
        (5, "-45.20", "new"),
        (6, "2000.00", "new"),
    ]
    assert shown["skipped"] == [{"number": 7, "reason": "Sin fecha.", "text": "Total · 1.954,80"}]
    assert (shown["bank_balance"], shown["bank_balance_date"]) == ("1954.80", "2026-10-15")
    assert shown["balance_then"] == "1954.80"  # it would match the bank
    assert movements(ana, account) == []


def test_import_creates_the_movements_with_their_kind(ana: TestClient, account: str) -> None:
    batch = do_import(ana, account, SEMICOLON_CSV)

    assert (batch["imported"], batch["skipped"]) == (2, 0)
    assert (batch["date_from"], batch["date_to"]) == ("2026-10-14", "2026-10-15")
    rows = ana.get("/api/transactions", params={"account_id": account}).json()["items"]
    assert [(r["kind"], r["source"], r["amount"]) for r in rows] == [
        ("expense", "import", "-45.20"),
        ("income", "import", "2000.00"),
    ]
    assert balance(ana, account) == "1954.80"


def test_same_day_movements_keep_the_bank_order(ana: TestClient, account: str) -> None:
    content = b"Fecha;Concepto;Importe\n02/10/2026;SEGUNDO;-2\n02/10/2026;PRIMERO;-1\n"
    do_import(ana, account, content)

    # Newest first, as in the file (both on the same day).
    assert [m[1] for m in movements(ana, account)] == ["SEGUNDO", "PRIMERO"]


def test_reimporting_an_overlapping_file_adds_only_what_is_new(
    ana: TestClient, account: str
) -> None:
    do_import(ana, account, SEMICOLON_CSV)
    header = "Fecha operación;Fecha valor;Concepto;Importe;Saldo\r\n".encode("cp1252")
    newer = SEMICOLON_CSV.replace(
        header, header + b"16/10/2026;16/10/2026;BAR PEPE;-3,50;1.951,30\r\n"
    )

    shown = preview(ana, account, newer)

    assert [(r["description"], r["status"]) for r in shown["rows"]] == [
        ("BAR PEPE", "new"),
        ("COMPRA TARJ. 1234 MERCADONA VALENCIA", "duplicate"),
        ("NÓMINA OCTUBRE", "duplicate"),
    ]
    do_import(ana, account, newer)
    assert len(movements(ana, account)) == 3


def test_the_same_purchase_twice_in_a_day_is_not_a_duplicate(ana: TestClient, account: str) -> None:
    once = b"Fecha;Concepto;Importe\n01/10/2026;CAFE;-1,50\n"
    do_import(ana, account, once)

    shown = preview(ana, account, once + b"01/10/2026;CAFE;-1,50\n")

    assert [r["status"] for r in shown["rows"]] == ["duplicate", "new"]


def test_a_movement_entered_by_hand_is_merged_not_repeated(ana: TestClient, account: str) -> None:
    by_hand = add(
        ana,
        account,
        "expense",
        "45.20",
        date="2026-10-13",
        description="Mercadona",
        category_id=category_id(ana, "Supermercado"),
    )

    shown = preview(ana, account, SEMICOLON_CSV)
    first = shown["rows"][0]
    assert (first["status"], first["match_id"], first["decisions"]) == (
        "match",
        by_hand["id"],
        ["merge", "import", "skip"],
    )
    batch = do_import(ana, account, SEMICOLON_CSV)

    assert (batch["imported"], batch["merged"]) == (1, 1)
    # Kept as entered (concept, category), now confirmed by the bank.
    assert movements(ana, account) == [
        ("2026-10-14", "NÓMINA OCTUBRE", "2000.00", None),
        ("2026-10-13", "Mercadona", "-45.20", by_hand["category_id"]),
    ]
    assert {r["status"] for r in preview(ana, account, SEMICOLON_CSV)["rows"]} == {"duplicate"}


def test_a_hand_mapping_for_unknown_columns(ana: TestClient, account: str) -> None:
    content = b"Dia;Que;Cuanto\n01/10/2026;Cine;-9,50\n"
    shown = preview(ana, account, content)
    assert shown["mapping"] is None
    assert shown["error"] == "Indica qué columna es la fecha, el concepto y el importe."
    assert shown["sample"] == [["01/10/2026", "Cine", "-9,50"]]

    mapping = {"date": "Dia", "description": ["Que"], "amount": "Cuanto"}
    shown = preview(ana, account, content, mapping=json.dumps(mapping))

    assert [(r["description"], r["amount"]) for r in shown["rows"]] == [("Cine", "-9.50")]


def test_templates_are_shared_and_recognised(ana: TestClient, bea: TestClient) -> None:
    mapping = {
        "date": "Fecha",
        "description": ["Descripción"],
        "debit": "Cargo",
        "credit": "Abono",
    }
    response = ana.post("/api/import-templates", json={"name": "Mi banco", "mapping": mapping})
    assert response.status_code == 201, response.text
    template_id = response.json()["id"]

    bea_account = str(new_account(bea)["id"])
    shown = preview(bea, bea_account, DEBIT_CREDIT_CSV)

    assert shown["template_id"] == template_id
    assert [r["amount"] for r in shown["rows"]] == ["-60.10", "15.00"]
    listed = bea.get("/api/import-templates").json()
    assert [(t["name"], t["mine"]) for t in listed] == [("Mi banco", False)]
    assert bea.delete(f"/api/import-templates/{template_id}").status_code == 403
    assert ana.delete(f"/api/import-templates/{template_id}").status_code == 204


def test_template_names_are_unique(ana: TestClient) -> None:
    mapping = {"date": "Fecha", "description": ["Concepto"], "amount": "Importe"}
    ana.post("/api/import-templates", json={"name": "Bankinter", "mapping": mapping})

    response = ana.post("/api/import-templates", json={"name": "bankinter", "mapping": mapping})

    assert response.status_code == 409


def test_save_the_mapping_as_a_template_while_importing(ana: TestClient, account: str) -> None:
    batch = do_import(ana, account, xlsx_statement(), save_template_as="Mi Excel")

    assert batch["template_name"] == "Mi Excel"
    assert [t["name"] for t in ana.get("/api/import-templates").json()] == ["Mi Excel"]


def test_import_only_the_chosen_rows(ana: TestClient, account: str) -> None:
    batch = do_import(ana, account, SEMICOLON_CSV, rows=[6])

    assert (batch["imported"], batch["skipped"]) == (1, 1)
    assert [m[1] for m in movements(ana, account)] == ["NÓMINA OCTUBRE"]


def test_undo_an_import(ana: TestClient, account: str) -> None:
    add(ana, account, "expense", "5", description="A mano")
    batch = do_import(ana, account, SEMICOLON_CSV)

    assert ana.delete(f"/api/imports/{batch['id']}").status_code == 204

    assert [m[1] for m in movements(ana, account)] == ["A mano"]
    assert ana.get("/api/imports").json() == []
    # Undone rows are new again.
    assert {r["status"] for r in preview(ana, account, SEMICOLON_CSV)["rows"]} == {"new"}


def test_imports_are_listed_newest_first(
    ana: TestClient, account: str, fake_clock: FakeClock
) -> None:
    do_import(ana, account, SEMICOLON_CSV)
    fake_clock.advance(minutes=1)
    do_import(ana, account, DEBIT_CREDIT_CSV)

    listed = ana.get("/api/imports", params={"account_id": account}).json()

    assert [b["date_from"] for b in listed] == ["2026-10-01", "2026-10-14"]


def test_rules_categorise_imported_rows(ana: TestClient, account: str) -> None:
    groceries = category_id(ana, "Supermercado")
    ana.post("/api/rules", json={"match_text": "mercadona", "category_id": groceries})

    shown = preview(ana, account, SEMICOLON_CSV)
    assert shown["rows"][0]["category_id"] == groceries
    do_import(ana, account, SEMICOLON_CSV)

    assert movements(ana, account)[0][3] == groceries


def test_errors_are_explained(ana: TestClient, account: str) -> None:
    def attempt(content: bytes, **form: str) -> Any:
        return ana.post(
            "/api/imports/preview",
            data={"account_id": account, **form},
            files={"file": ("x.pdf", content, "application/pdf")},
        )

    assert attempt(b"%PDF-1.4").json()["error"]["message"] == (
        "No se puede leer el PDF. ¿Está dañado?"
    )
    assert attempt(b"x" * (5 * 1024 * 1024 + 1)).status_code == 413
    incomplete = attempt(SEMICOLON_CSV, mapping=json.dumps({"date": "Fecha"}))
    assert incomplete.status_code == 422
    wrong = preview(
        ana,
        account,
        SEMICOLON_CSV,
        mapping=json.dumps({"date": "Fecha", "description": ["X"], "amount": "Y"}),
    )
    assert wrong["error"].startswith("No encuentro las columnas")
    assert wrong["columns"][0] == "Fecha operación"  # the file's columns, to map them


def test_nothing_chosen_nothing_imported(ana: TestClient, account: str) -> None:
    shown = preview(ana, account, SEMICOLON_CSV)
    response = ana.post(
        "/api/imports",
        data={
            "account_id": account,
            "mapping": json.dumps(shown["mapping"]),
            "decisions": json.dumps({"5": "skip"}),
        },
        files={"file": ("e.csv", SEMICOLON_CSV, CSV)},
    )

    assert response.status_code == 422
    assert response.json()["error"]["message"] == "No has elegido ningún movimiento."


def test_nobody_imports_into_someone_elses_account(bea: TestClient, account: str) -> None:
    response = bea.post(
        "/api/imports/preview",
        data={"account_id": account},
        files={"file": ("e.csv", SEMICOLON_CSV, CSV)},
    )
    assert response.status_code == 404


def test_nobody_undoes_someone_elses_import(ana: TestClient, bea: TestClient, account: str) -> None:
    batch = do_import(ana, account, SEMICOLON_CSV)

    assert bea.delete(f"/api/imports/{batch['id']}").status_code == 404
    assert bea.get("/api/imports").json() == []


def test_bankinter_pdf_statement(ana: TestClient, account: str) -> None:
    def send(path: str, **form: str) -> Any:
        return ana.post(
            path,
            data={"account_id": account, **form},
            files={"file": ("extracto.pdf", bankinter_pdf(), "application/pdf")},
        )

    shown = send("/api/imports/preview").json()

    assert (shown["reader"], shown["mapping"], shown["columns"]) == (
        "Bankinter (extracto PDF)",
        None,
        [],
    )
    assert [r["amount"] for r in shown["rows"]] == [
        "-12.24",
        "-187.76",
        "1500.00",
        "-100.00",
        "25.50",
        "-425.50",
    ]
    assert (shown["bank_balance"], shown["bank_balance_date"]) == ("2000.00", "2026-09-30")

    decisions = json.dumps({str(r["number"]): "import" for r in shown["rows"]})
    batch = send("/api/imports", decisions=decisions).json()

    assert (batch["imported"], batch["template_name"]) == (6, "Bankinter (extracto PDF)")
    # Imported again, nothing is new.
    assert {r["status"] for r in send("/api/imports/preview").json()["rows"]} == {"duplicate"}


def test_a_pdf_whose_balances_do_not_add_up_is_refused(ana: TestClient, account: str) -> None:
    response = ana.post(
        "/api/imports/preview",
        data={"account_id": account},
        files={"file": ("e.pdf", bankinter_pdf(broken=True), "application/pdf")},
    )

    assert response.status_code == 422
    assert "no cuadran" in response.json()["error"]["message"]


def test_history_before_the_opening_date_keeps_todays_balance(ana: TestClient) -> None:
    """The account was created with today's balance; older movements are already in it."""
    today = str(new_account(ana, opening_date="2026-10-15", opening_balance="2298")["id"])
    content = (
        b"Fecha;Concepto;Importe;Saldo\n"
        b"30/09/2026;RECIBO VISA;-880,30;793,71\n"
        b"01/09/2026;NOMINA;1.566,67;2.805,71\n"
    )

    shown = preview(ana, today, content)
    do_import(ana, today, content)

    # Before the anchor, the balance is worked out backwards from it: nothing was imported
    # between 30/09 and today, so MiAhorro says 2.298 where the bank said 793,71 (October is
    # missing).
    assert (shown["bank_balance"], shown["balance_then"]) == ("793.71", "2298.00")
    assert balance(ana, today) == "2298.00"
    listed = {a["id"]: a["balance"] for a in ana.get("/api/accounts").json()}
    assert listed[today] == "2298.00"


def test_balance_before_the_anchor_matches_the_bank_when_nothing_is_missing(
    ana: TestClient,
) -> None:
    account = str(new_account(ana, opening_date="2026-10-01", opening_balance="793.71")["id"])
    content = b"Fecha;Concepto;Importe;Saldo\n30/09/2026;RECIBO VISA;-880,30;793,71\n"

    shown = preview(ana, account, content)

    assert (shown["bank_balance"], shown["balance_then"]) == ("793.71", "793.71")


def test_a_decision_the_row_does_not_allow_is_refused(ana: TestClient, account: str) -> None:
    shown = preview(ana, account, SEMICOLON_CSV)
    response = ana.post(
        "/api/imports",
        data={
            "account_id": account,
            "mapping": json.dumps(shown["mapping"]),
            "decisions": json.dumps({"5": "merge"}),  # a new row has nothing to merge with
        },
        files={"file": ("e.csv", SEMICOLON_CSV, CSV)},
    )

    assert response.status_code == 409


def test_undo_puts_back_a_merged_movement(ana: TestClient, account: str) -> None:
    add(ana, account, "expense", "45.20", date="2026-10-13", description="Mercadona")
    batch = do_import(ana, account, SEMICOLON_CSV)

    ana.delete(f"/api/imports/{batch['id']}").raise_for_status()

    assert movements(ana, account) == [("2026-10-13", "Mercadona", "-45.20", None)]
    assert preview(ana, account, SEMICOLON_CSV)["rows"][0]["status"] == "match"


def test_the_other_side_of_a_transfer_is_recognised(ana: TestClient, account: str) -> None:
    savings = str(new_account(ana, name="Ahorro", opening_date="2026-10-01")["id"])
    add(ana, savings, "income", "45.20", date="2026-10-14", description="Desde la nómina")

    shown = preview(ana, account, SEMICOLON_CSV)
    first = shown["rows"][0]
    assert (first["status"], first["transfer_account_id"]) == ("transfer", savings)

    batch = do_import(ana, account, SEMICOLON_CSV)
    rows = ana.get("/api/transactions").json()["items"]
    legs = [r for r in rows if r["kind"] == "transfer"]
    assert {(r["account_id"], r["amount"]) for r in legs} == {
        (account, "-45.20"),
        (savings, "45.20"),
    }
    assert legs[0]["transfer_id"] == legs[1]["transfer_id"]

    # Undo: the savings movement is a plain income again.
    ana.delete(f"/api/imports/{batch['id']}").raise_for_status()
    rows = ana.get("/api/transactions").json()["items"]
    assert [(r["account_id"], r["kind"], r["transfer_id"]) for r in rows] == [
        (savings, "income", None)
    ]


def test_a_rule_turns_the_card_bill_into_a_transfer(ana: TestClient, account: str) -> None:
    card = str(new_account(ana, name="Visa", kind="credit_card", opening_date="2026-10-01")["id"])
    ana.post(
        "/api/rules", json={"match_text": "mercadona", "transfer_account_id": card}
    ).raise_for_status()

    shown = preview(ana, account, SEMICOLON_CSV)
    assert (shown["rows"][0]["status"], shown["rows"][0]["transfer_account_id"]) == (
        "transfer",
        card,
    )
    do_import(ana, account, SEMICOLON_CSV)

    # The card account gets the other leg: its debt goes down by what the bank paid.
    card_rows = ana.get("/api/transactions", params={"account_id": card}).json()["items"]
    assert [(r["kind"], r["amount"], r["description"]) for r in card_rows] == [
        ("transfer", "45.20", f"Transferencia desde {_name(ana, account)}")
    ]
    # Not an expense: the purchases were already counted in the card.
    assert ana.get("/api/transactions", params={"kind": "expense"}).json()["total"] == 0


def _name(client: TestClient, account_id: str) -> str:
    return str(client.get(f"/api/accounts/{account_id}").json()["name"])

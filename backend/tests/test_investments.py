"""Investments (RF-INV-01, 02, 03, 05). Today is 15/10/2026 (fake clock)."""

from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.test_accounts import new_account
from tests.test_imports import do_import, preview
from tests.test_transactions import balance, category_id


def new_investment(client: TestClient, **fields: Any) -> Any:
    body = {"name": "Fondo indexado", "kind": "fund", **fields}
    response = client.post("/api/investments", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def operate(client: TestClient, investment: Any, **fields: Any) -> Any:
    response = client.post(f"/api/investments/{investment['id']}/operations", json=fields)
    assert response.status_code == 201, response.text
    return response.json()


def detail(client: TestClient, investment: Any) -> Any:
    return client.get(f"/api/investments/{investment['id']}").json()


@pytest.fixture
def bank(ana: TestClient) -> str:
    return str(new_account(ana, opening_balance="20000")["id"])


# --- Investments ------------------------------------------------------------------------------


def test_isin_is_checked_and_unique(ana: TestClient) -> None:
    fund = new_investment(ana, isin=" ie00b4l5y983 ", ticker=" iwda ")

    assert (fund["isin"], fund["ticker"]) == ("IE00B4L5Y983", "IWDA")
    bad = ana.post("/api/investments", json={"name": "X", "isin": "IE00B4L5Y984"})
    assert bad.status_code == 422
    assert "ISIN no es válido" in bad.json()["error"]["message"]
    twin = ana.post("/api/investments", json={"name": "Otro", "isin": "IE00B4L5Y983"})
    assert twin.status_code == 409
    assert "misma inversión" in twin.json()["error"]["message"]


def test_nobody_else_sees_them(ana: TestClient, bea: TestClient) -> None:
    fund = new_investment(ana)

    assert bea.get("/api/investments").json() == []
    assert bea.get(f"/api/investments/{fund['id']}").status_code == 404
    response = bea.post(
        f"/api/investments/{fund['id']}/operations",
        json={"date": "2026-01-10", "kind": "buy", "units": "1", "amount": "10"},
    )
    assert response.status_code == 404


# --- Purchases and sales ----------------------------------------------------------------------


def test_a_purchase_takes_the_money_from_the_account(ana: TestClient, bank: str) -> None:
    fund = new_investment(ana, account_id=bank)
    op = operate(
        ana,
        fund,
        date="2026-01-10",
        kind="buy",
        units="10.5",
        amount="1050",
        fee="2.5",
        cash_account_id=bank,
    )

    assert (op["price"], op["cash_account_id"]) == ("100", bank)
    assert balance(ana, bank) == "18947.50"
    movement = ana.get(f"/api/transactions/{op['transaction_id']}").json()
    assert (movement["kind"], movement["amount"]) == ("investment", "-1052.50")
    assert movement["description"] == "Compra de Fondo indexado"
    state = detail(ana, fund)
    assert (state["units"], state["cost"], state["average_cost"]) == (
        "10.5",
        "1052.50",
        "100.238095",
    )
    # Not an expense: the savings rate does not move.
    periods = ana.get("/api/savings-rate").json()["periods"]
    assert all(p["expenses"] == "0.00" for p in periods)


def test_its_movement_only_changes_from_the_investment(ana: TestClient, bank: str) -> None:
    fund = new_investment(ana)
    op = operate(
        ana, fund, date="2026-01-10", kind="buy", units="1", amount="100", cash_account_id=bank
    )
    url = f"/api/transactions/{op['transaction_id']}"

    assert ana.patch(url, json={"amount": "50"}).status_code == 422
    assert ana.patch(url, json={"description": "Fondo MSCI"}).status_code == 200


def test_a_sale_by_fifo(ana: TestClient, bank: str) -> None:
    fund = new_investment(ana)
    operate(ana, fund, date="2026-01-10", kind="buy", units="10", amount="1000", fee="1")
    operate(ana, fund, date="2026-02-10", kind="buy", units="10", amount="1200", fee="1")
    sale = operate(
        ana,
        fund,
        date="2026-03-10",
        kind="sell",
        units="15",
        amount="1950",
        fee="2",
        withholding="65.84",
        cash_account_id=bank,
    )

    assert sale["gain"] == "346.50"  # 1.948 received - (1.001 + 600,50)
    assert balance(ana, bank) == str(Decimal("20000") + Decimal("1950") - 2 - Decimal("65.84"))
    state = detail(ana, fund)
    assert (state["units"], state["cost"]) == ("5", "600.50")
    assert state["lots"] == [{"acquired": "2026-02-10", "units": "5", "cost": "600.50"}]
    assert (state["realized_year"], state["withholding_year"]) == ("346.50", "65.84")


def test_cannot_sell_what_is_not_there(ana: TestClient, bank: str) -> None:
    fund = new_investment(ana)
    operate(ana, fund, date="2026-01-10", kind="buy", units="10", amount="1000")

    response = ana.post(
        f"/api/investments/{fund['id']}/operations",
        json={
            "date": "2026-01-09",
            "kind": "sell",
            "units": "5",
            "amount": "500",
            "cash_account_id": bank,
        },
    )

    assert response.status_code == 409
    assert "09/01/2026" in response.json()["error"]["message"]
    assert len(ana.get(f"/api/investments/{fund['id']}/operations").json()) == 1
    assert balance(ana, bank) == "20000.00"


def test_changing_a_purchase_cannot_break_a_later_sale(ana: TestClient) -> None:
    fund = new_investment(ana)
    first = operate(ana, fund, date="2026-01-10", kind="buy", units="10", amount="1000")
    operate(ana, fund, date="2026-03-10", kind="sell", units="8", amount="900")
    url = f"/api/investments/{fund['id']}/operations/{first['id']}"

    smaller = ana.put(
        url, json={"date": "2026-01-10", "kind": "buy", "units": "5", "amount": "500"}
    )
    assert smaller.status_code == 409
    assert ana.delete(url).status_code == 409
    assert detail(ana, fund)["units"] == "2"


def test_editing_an_operation_redoes_its_movement(ana: TestClient, bank: str) -> None:
    fund = new_investment(ana)
    op = operate(
        ana, fund, date="2026-01-10", kind="buy", units="10", amount="1000", cash_account_id=bank
    )
    url = f"/api/investments/{fund['id']}/operations/{op['id']}"

    changed = ana.put(
        url,
        json={
            "date": "2026-01-12",
            "kind": "buy",
            "units": "10",
            "amount": "1100",
            "cash_account_id": bank,
        },
    ).json()
    assert balance(ana, bank) == "18900.00"
    assert changed["transaction_id"] != op["transaction_id"]
    assert ana.delete(url).status_code == 204
    assert balance(ana, bank) == "20000.00"


# --- Transfers and splits ---------------------------------------------------------------------


def test_a_transfer_between_funds_keeps_dates_and_costs(ana: TestClient) -> None:
    source = new_investment(ana, name="Fondo A")
    target = new_investment(ana, name="Fondo B")
    operate(ana, source, date="2020-01-10", kind="buy", units="10", amount="1000")
    operate(ana, source, date="2021-05-05", kind="buy", units="10", amount="1500")
    operate(
        ana,
        source,
        date="2025-06-01",
        kind="transfer",
        units="15",
        amount="2600",
        target_investment_id=target["id"],
        target_units="30",
    )

    assert detail(ana, source)["lots"] == [
        {"acquired": "2021-05-05", "units": "5", "cost": "750.00"}
    ]
    assert detail(ana, target)["lots"] == [
        {"acquired": "2020-01-10", "units": "20", "cost": "1000.00"},
        {"acquired": "2021-05-05", "units": "10", "cost": "750.00"},
    ]
    received = ana.get(f"/api/investments/{target['id']}/operations").json()
    assert [(op["kind"], op["direction"]) for op in received] == [("transfer", "in")]
    # The receiving fund cannot go while the transfer is there.
    assert ana.delete(f"/api/investments/{target['id']}").status_code == 409


def test_only_funds_and_pension_plans_transfer(ana: TestClient) -> None:
    etf = new_investment(ana, name="ETF", kind="etf")
    fund = new_investment(ana, name="Fondo")
    operate(ana, etf, date="2026-01-10", kind="buy", units="10", amount="1000")

    response = ana.post(
        f"/api/investments/{etf['id']}/operations",
        json={
            "date": "2026-02-10",
            "kind": "transfer",
            "units": "10",
            "amount": "1000",
            "target_investment_id": fund["id"],
            "target_units": "10",
        },
    )

    assert response.status_code == 422


def test_a_split(ana: TestClient) -> None:
    shares = new_investment(ana, name="Acciones", kind="stock")
    operate(ana, shares, date="2026-01-10", kind="buy", units="10", amount="1000")
    operate(ana, shares, date="2026-02-01", kind="split", split_from=1, split_to=2)

    state = detail(ana, shares)
    assert (state["units"], state["cost"]) == ("20", "1000.00")


# --- Dividends and prices ---------------------------------------------------------------------


def test_a_dividend_is_income(ana: TestClient, bank: str) -> None:
    shares = new_investment(ana, name="Acciones", kind="stock")
    operate(ana, shares, date="2026-01-10", kind="buy", units="10", amount="1000")
    op = operate(
        ana,
        shares,
        date="2026-06-01",
        kind="dividend",
        amount="50",
        withholding="9.50",
        cash_account_id=bank,
    )

    movement = ana.get(f"/api/transactions/{op['transaction_id']}").json()
    assert (movement["kind"], movement["amount"]) == ("income", "40.50")
    assert movement["category_id"] == category_id(ana, "Intereses y dividendos")
    state = detail(ana, shares)
    assert (state["dividends_year"], state["withholding_year"]) == ("50.00", "9.50")


def test_value_from_the_latest_price(ana: TestClient) -> None:
    fund = new_investment(ana)
    operate(ana, fund, date="2026-01-10", kind="buy", units="10", amount="1000")

    state = detail(ana, fund)
    assert (state["price"], state["price_source"], state["value"]) == (
        "100",
        "operation",
        "1000.00",
    )

    url = f"/api/investments/{fund['id']}/prices"
    ana.put(url, json={"date": "2026-10-14", "price": "112.3456"}).raise_for_status()
    ana.put(url, json={"date": "2026-10-14", "price": "112.5"}).raise_for_status()  # replaces
    state = detail(ana, fund)
    assert (state["price"], state["price_date"], state["price_source"]) == (
        "112.5",
        "2026-10-14",
        "manual",
    )
    assert (state["value"], state["gain"], state["gain_percent"]) == ("1125.00", "125.00", "12.50")
    assert len(ana.get(url).json()) == 1
    assert ana.put(url, json={"date": "2026-10-16", "price": "1"}).status_code == 422


# --- Portfolio and tax report -----------------------------------------------------------------


def test_portfolio_totals(ana: TestClient) -> None:
    fund = new_investment(ana)
    shares = new_investment(ana, name="Acciones", kind="stock")
    operate(ana, fund, date="2026-01-10", kind="buy", units="10", amount="1000")
    operate(ana, shares, date="2026-01-10", kind="buy", units="4", amount="400")
    ana.put(f"/api/investments/{shares['id']}/prices", json={"date": "2026-10-01", "price": "150"})

    total = ana.get("/api/portfolio").json()

    assert (total["value"], total["cost"], total["gain"]) == ("1600.00", "1400.00", "200.00")
    assert total["gain_percent"] == "14.29"
    assert total["by_kind"] == [
        {"kind": "fund", "value": "1000.00"},
        {"kind": "stock", "value": "600.00"},
    ]


def test_tax_report_of_the_year(ana: TestClient) -> None:
    shares = new_investment(ana, name="Acciones", kind="stock")
    plan = new_investment(ana, name="Plan", kind="pension_plan")
    operate(ana, shares, date="2025-03-10", kind="buy", units="10", amount="1000")
    operate(ana, shares, date="2026-03-10", kind="sell", units="10", amount="800")  # -200
    operate(ana, shares, date="2026-04-20", kind="buy", units="5", amount="390")  # bought back
    operate(ana, shares, date="2026-06-01", kind="dividend", amount="20", withholding="3.80")
    operate(ana, plan, date="2020-01-01", kind="buy", units="100", amount="1000")
    operate(ana, plan, date="2026-05-01", kind="sell", units="100", amount="1500")

    report = ana.get("/api/portfolio/tax-report", params={"year": 2026}).json()

    stock_sale, rescue = report["sales"]
    assert (stock_sale["gain"], stock_sale["repurchase_warning"]) == ("-200.00", True)
    assert stock_sale["parts"] == [
        {
            "acquired": "2025-03-10",
            "units": "10",
            "cost": "1000.00",
            "proceeds": "800.00",
            "gain": "-200.00",
        }
    ]
    assert (rescue["taxable"], rescue["proceeds"]) == (False, "1500.00")
    assert (report["gains"], report["losses"], report["net"]) == ("0.00", "-200.00", "-200.00")
    assert report["pension_rescues"] == "1500.00"
    assert (report["dividends_gross"], report["dividends_withholding"]) == ("20.00", "3.80")
    empty = ana.get("/api/portfolio/tax-report", params={"year": 2025}).json()
    assert empty["sales"] == []


def test_deleting_an_investment_takes_its_unconfirmed_movements(ana: TestClient, bank: str) -> None:
    fund = new_investment(ana)
    operate(
        ana, fund, date="2026-01-10", kind="buy", units="10", amount="1000", cash_account_id=bank
    )

    assert ana.delete(f"/api/investments/{fund['id']}").status_code == 204
    assert balance(ana, bank) == "20000.00"
    assert ana.get("/api/investments").json() == []


def test_the_bank_statement_confirms_the_movement(ana: TestClient, bank: str) -> None:
    fund = new_investment(ana)
    op = operate(
        ana, fund, date="2026-10-13", kind="buy", units="10", amount="1000", cash_account_id=bank
    )
    statement = (
        "Fecha operación;Fecha valor;Concepto;Importe;Saldo\r\n"
        "14/10/2026;14/10/2026;SUSCRIPCION FONDO INDEXADO;-1.000,00;19.000,00\r\n"
    ).encode("cp1252")

    shown = preview(ana, bank, statement)

    assert (shown["rows"][0]["status"], shown["rows"][0]["match_id"]) == (
        "match",
        op["transaction_id"],
    )
    do_import(ana, bank, statement)
    assert balance(ana, bank) == "19000.00"  # merged, not counted twice

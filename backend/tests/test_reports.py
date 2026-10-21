"""Dashboard, reports and export (RF-INF-01…04, RF-PRE-09, RF-IMP-04). Today is 15/10/2026."""

import csv
import datetime as dt
import io
import json
import zipfile
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.networth import month_ends
from app.reports import comparison_ranges, periods_in
from tests.test_accounts import new_account
from tests.test_goals import new_goal, put_aside
from tests.test_investments import new_investment, operate
from tests.test_loans import new_loan, schedule
from tests.test_transactions import add, category_id, transfer

D = Decimal


# --- Pure helpers -----------------------------------------------------------------------------


def test_month_ends() -> None:
    assert month_ends(dt.date(2026, 1, 15), dt.date(2026, 4, 10)) == [
        dt.date(2026, 1, 31),
        dt.date(2026, 2, 28),
        dt.date(2026, 3, 31),
        dt.date(2026, 4, 10),
    ]
    assert month_ends(dt.date(2026, 3, 31), dt.date(2026, 3, 31)) == [dt.date(2026, 3, 31)]


def test_periods_by_financial_month_and_year() -> None:
    months = periods_in(dt.date(2026, 1, 10), dt.date(2026, 3, 5), "month", 25)
    assert months == [
        (dt.date(2026, 1, 10), dt.date(2026, 1, 24)),
        (dt.date(2026, 1, 25), dt.date(2026, 2, 24)),
        (dt.date(2026, 2, 25), dt.date(2026, 3, 5)),
    ]
    years = periods_in(dt.date(2025, 6, 1), dt.date(2026, 2, 1), "year", 1)
    assert years == [
        (dt.date(2025, 6, 1), dt.date(2025, 12, 31)),
        (dt.date(2026, 1, 1), dt.date(2026, 2, 1)),
    ]


@pytest.mark.parametrize(
    ("start", "end", "current", "previous", "last_year"),
    [
        # This month so far: the same days of last month
        ("2026-10-01", "2026-10-31", ("2026-10-01", "2026-10-15"),
         ("2026-09-01", "2026-09-15"), ("2025-10-01", "2025-10-15")),
        # A whole past month against the whole previous one
        ("2026-03-01", "2026-03-31", ("2026-03-01", "2026-03-31"),
         ("2026-02-01", "2026-02-28"), ("2025-03-01", "2025-03-31")),
        # A year against the one before
        ("2025-01-01", "2025-12-31", ("2025-01-01", "2025-12-31"),
         ("2024-01-01", "2024-12-31"), ("2024-01-01", "2024-12-31")),
        # Any dates: as many days just before
        ("2026-05-10", "2026-05-19", ("2026-05-10", "2026-05-19"),
         ("2026-04-30", "2026-05-09"), ("2025-05-10", "2025-05-19")),
    ],
)  # fmt: skip
def test_comparison_ranges(
    start: str,
    end: str,
    current: tuple[str, str],
    previous: tuple[str, str],
    last_year: tuple[str, str],
) -> None:
    ranges = comparison_ranges(
        dt.date.fromisoformat(start), dt.date.fromisoformat(end), dt.date(2026, 10, 15), 1
    )

    def iso(pair: tuple[dt.date, dt.date]) -> tuple[str, str]:
        return (pair[0].isoformat(), pair[1].isoformat())

    assert (iso(ranges.current), iso(ranges.previous), iso(ranges.last_year)) == (
        current,
        previous,
        last_year,
    )


# --- Net worth --------------------------------------------------------------------------------


@pytest.fixture
def wealth(ana: TestClient) -> dict[str, Any]:
    bank = str(new_account(ana, opening_balance="5000")["id"])
    card = str(
        new_account(ana, name="Tarjeta", kind="credit_card", opening_date="2026-06-01")["id"]
    )
    add(ana, bank, "income", "2000", date="2026-02-01")
    add(ana, bank, "expense", "300", date="2026-03-10")
    add(ana, bank, "expense", "100", date="2026-10-02")
    add(ana, card, "expense", "250", date="2026-06-15")
    fund = new_investment(ana)
    operate(ana, fund, date="2026-02-15", kind="buy", units="10", amount="1000")
    ana.put(
        f"/api/investments/{fund['id']}/prices", json={"date": "2026-10-01", "price": "120"}
    ).raise_for_status()
    car = new_loan(ana)  # 12.000 € signed on 10/01/2026, first instalment 05/02/2026
    new_loan(
        ana,
        name="A Luis",
        kind="p2p_lent",
        principal="1000",
        signed_on="2026-04-01",
        first_payment="2026-05-01",
        term_months=10,
        fixed_rate="0",
    )
    return {"bank": bank, "card": card, "car": car, "rows": schedule(ana, car)}


def _point(report: Any, date: str) -> Any:
    return next(p for p in report["points"] if p["date"] == date)


def test_net_worth_in_the_past_adds_up(ana: TestClient, wealth: dict[str, Any]) -> None:
    report = ana.get("/api/reports/net-worth", params={"start": "2026-01-01"}).json()

    march = _point(report, "2026-03-31")
    # The card account was opened in June: it is not counted before.
    assert march["accounts"] == "6700.00"  # 5.000 + 2.000 - 300
    assert march["investments"] == "1000.00"  # 10 units at the purchase price
    assert march["lent"] == "0.00"  # not lent yet
    assert march["debts"] == wealth["rows"][1]["outstanding"]  # after two instalments
    for point in report["points"]:
        parts = D(point["accounts"]) + D(point["investments"]) + D(point["lent"])
        assert D(point["total"]) == parts - D(point["debts"])
    assert [p["date"] for p in report["points"]][:2] == ["2026-01-31", "2026-02-28"]
    assert report["points"][-1]["date"] == "2026-10-15"
    assert report["start"] == "2026-01-01"


def test_net_worth_today(ana: TestClient, wealth: dict[str, Any]) -> None:
    today = ana.get("/api/dashboard").json()["net_worth"]

    assert today["accounts"] == "6350.00"  # 6.700 - 100 - 250 of the card
    assert today["investments"] == "1200.00"  # at the price of 01/10
    assert today["lent"] == "400.00"  # six of the ten payments made
    loan = ana.get(f"/api/loans/{wealth['car']['id']}").json()
    assert today["debts"] == loan["outstanding"]


def test_net_worth_report_starts_with_the_data(ana: TestClient) -> None:
    assert ana.get("/api/reports/net-worth").json() == {"start": None, "points": []}

    new_account(ana, opening_date="2026-09-10", opening_balance="100")
    report = ana.get("/api/reports/net-worth").json()

    assert [p["date"] for p in report["points"]] == ["2026-09-30", "2026-10-15"]


# --- Dashboard --------------------------------------------------------------------------------


def test_dashboard(ana: TestClient, wealth: dict[str, Any]) -> None:
    goal = new_goal(ana)
    put_aside(ana, goal, wealth["bank"], "500").raise_for_status()
    add(ana, wealth["bank"], "income", "1500", date="2026-10-01")

    board = ana.get("/api/dashboard").json()

    assert board["previous"]["date"] == "2026-09-30"
    assert board["previous"]["accounts"] == "6450.00"
    # Everyday money: the bank and the card, minus the 500 € set aside
    assert board["available"] == "7350.00"  # 8.100 - 250 - 500
    assert board["reserved"] == "500.00"
    assert board["month"]["start"] == "2026-10-01"
    assert (board["month"]["income"], board["month"]["expenses"]) == ("1500.00", "-100.00")


# --- Income and expenses ----------------------------------------------------------------------


def test_cash_flow_by_month_and_year(ana: TestClient, wealth: dict[str, Any]) -> None:
    savings = str(new_account(ana, name="Ahorro", kind="savings")["id"])
    transfer(ana, wealth["bank"], savings, "700", date="2026-02-20").raise_for_status()
    fund = new_investment(ana, name="Otro fondo")
    operate(
        ana,
        fund,
        date="2026-02-21",
        kind="buy",
        units="1",
        amount="100",
        cash_account_id=wealth["bank"],
    )

    months = ana.get(
        "/api/reports/cash-flow", params={"start": "2026-01-01", "end": "2026-03-31"}
    ).json()
    year = ana.get(
        "/api/reports/cash-flow",
        params={"start": "2026-01-01", "end": "2026-10-15", "group": "year"},
    ).json()

    assert [(p["start"], p["income"], p["expenses"]) for p in months["periods"]] == [
        ("2026-01-01", "0.00", "0.00"),
        ("2026-02-01", "2000.00", "0.00"),  # the transfer and the investment do not count
        ("2026-03-01", "0.00", "-300.00"),
    ]
    assert (months["total"]["saved"], months["total"]["rate"]) == ("1700.00", "85.0")
    assert len(year["periods"]) == 1
    assert year["total"]["expenses"] == "-650.00"


# --- Spending ---------------------------------------------------------------------------------


@pytest.fixture
def spent(ana: TestClient) -> None:
    bank = str(new_account(ana, opening_date="2025-01-01", opening_balance="3000")["id"])
    food = category_id(ana, "Supermercado")
    add(
        ana,
        bank,
        "expense",
        "50",
        date="2026-10-05",
        description="COMPRA TARJ. 1234 MERCADONA VALENCIA",
        category_id=food,
        tags=["casa"],
    )
    add(
        ana,
        bank,
        "expense",
        "30",
        date="2026-10-08",
        description="Bar Pepe",
        category_id=category_id(ana, "Restaurantes"),
        tags=["ocio"],
    )
    add(ana, bank, "expense", "40", date="2026-09-10", description="Mercadona", category_id=food)
    add(ana, bank, "expense", "99", date="2026-09-20", description="Mercadona", category_id=food)
    add(ana, bank, "expense", "20", date="2025-10-03", description="Cine")


def test_spending_by_category_against_last_month_and_last_year(
    ana: TestClient, spent: None
) -> None:
    report = ana.get("/api/reports/spending").json()

    assert (report["current"], report["previous"], report["last_year"]) == (
        {"start": "2026-10-01", "end": "2026-10-15"},
        {"start": "2026-09-01", "end": "2026-09-15"},  # the same days: 99 € of the 20th out
        {"start": "2025-10-01", "end": "2025-10-15"},
    )
    assert (report["total"], report["total_previous"], report["total_last_year"]) == (
        "80.00",
        "40.00",
        "20.00",
    )
    (food,) = report["lines"]  # uncategorised cinema only last year: left out
    assert (food["label"], food["amount"], food["previous"]) == ("Alimentación", "80.00", "40.00")
    assert [(c["label"], c["amount"], c["previous"]) for c in food["children"]] == [
        ("Supermercado", "50.00", "40.00"),
        ("Restaurantes", "30.00", "0.00"),
    ]


def test_spending_by_merchant_and_tag(ana: TestClient, spent: None) -> None:
    merchants = ana.get("/api/reports/spending", params={"by": "merchant"}).json()
    tags = ana.get("/api/reports/spending", params={"by": "tag"}).json()

    assert [(m["label"], m["amount"], m["previous"]) for m in merchants["lines"]] == [
        ("Mercadona", "50.00", "40.00"),  # the bank's concept and a typed one, together
        ("Bar Pepe", "30.00", "0.00"),
    ]
    assert [(t["label"], t["amount"]) for t in tags["lines"]] == [
        ("casa", "50.00"),
        ("ocio", "30.00"),
    ]


def test_spending_between_any_dates(ana: TestClient, spent: None) -> None:
    report = ana.get(
        "/api/reports/spending", params={"start": "2026-09-01", "end": "2026-09-30"}
    ).json()

    assert report["total"] == "139.00"
    assert report["previous"] == {"start": "2026-08-01", "end": "2026-08-31"}


# --- Export -----------------------------------------------------------------------------------


def test_export_json_has_everything_and_reads_back(
    ana: TestClient, bea: TestClient, wealth: dict[str, Any]
) -> None:
    new_account(bea, name="De Bea")
    response = ana.get("/api/export.json")

    assert response.headers["content-disposition"] == (
        'attachment; filename="miahorro-2026-10-15.json"'
    )
    data = json.loads(response.content)
    assert (data["format"], data["version"]) == ("miahorro-export", 1)
    assert data["profile"]["email"] == "ana@example.com"
    tables = data["tables"]
    assert {a["name"] for a in tables["accounts"]} == {"Nómina", "Tarjeta"}
    assert len(tables["transactions"]) == 4
    assert len(tables["loans"]) == 2
    assert len(tables["investment_operations"]) == 1
    assert tables["investment_prices"][0]["price"] == "120.000000"
    assert {"transactions", "categories", "savings_goals", "calculator_scenarios"} <= set(tables)
    text = response.text
    for secret in ("password_hash", "totp_secret", "token_hash", "user_id"):
        assert secret not in text
    # Balances can be worked out again from what was exported.
    bank = next(a for a in tables["accounts"] if a["id"] == wealth["bank"])
    moves = [t for t in tables["transactions"] if t["account_id"] == wealth["bank"]]
    balance = D(bank["opening_balance"]) + sum((D(t["amount"]) for t in moves), D(0))
    assert balance == D(ana.get(f"/api/accounts/{wealth['bank']}").json()["balance"]) == D(6600)


def test_export_zip_has_a_csv_per_table(ana: TestClient, wealth: dict[str, Any]) -> None:
    response = ana.get("/api/export.zip")

    archive = zipfile.ZipFile(io.BytesIO(response.content))
    names = set(archive.namelist())
    assert {"LEEME.txt", "perfil.json", "accounts.csv", "transactions.csv"} <= names
    text = archive.read("transactions.csv").decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text), delimiter=";"))
    assert len(rows) == 4
    amounts = sorted(D(row["amount"].replace(",", ".")) for row in rows)
    assert amounts == [D("-300.00"), D("-250.00"), D("-100.00"), D("2000.00")]

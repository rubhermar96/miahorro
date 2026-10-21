"""Performance with a realistic load (RNF-08): 50.000 movements over three years. Every screen's
request answers in under two seconds. Today is 15/10/2026 (fake clock)."""

import datetime as dt
import os
import random
import time
import uuid
from decimal import Decimal
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import insert, select

from app.models.transactions import Category, Transaction
from app.models.user import User
from tests.test_accounts import new_account

MOVEMENTS = int(os.environ.get("MIAHORRO_PERF_MOVEMENTS", "50000"))
LIMIT_SECONDS = 2.0
MERCHANTS = [
    "COMPRA TARJ. 1234 MERCADONA VALENCIA",
    "COMPRA TARJ. 1234 CARREFOUR",
    "Bar Pepe",
    "REPSOL ESTACION 22",
    "AMAZON EU SARL",
    "Farmacia Lopez",
    "RECIBO IBERDROLA",
    "Netflix",
    "Cine Lys",
    "Uber trip",
]


def _load(app: FastAPI, accounts: list[str]) -> None:
    rng = random.Random(2026)  # noqa: S311  # synthetic data, the same every run
    with app.state.session_factory() as db:
        user = db.scalar(select(User).where(User.email == "ana@example.com"))
        assert user is not None
        expense = [c.id for c in db.scalars(select(Category).where(Category.kind == "expense"))]
        income = [c.id for c in db.scalars(select(Category).where(Category.kind == "income"))]
        start = dt.date(2023, 10, 16)
        now = dt.datetime(2026, 10, 15, tzinfo=dt.UTC)
        rows: list[dict[str, Any]] = []
        for number in range(MOVEMENTS):
            date = start + dt.timedelta(days=number * 1095 // MOVEMENTS)
            is_income = number % 25 == 0
            amount = Decimal(rng.randint(100, 300_000)) / 100
            rows.append(
                {
                    "id": uuid.uuid4(),
                    "user_id": user.id,
                    "account_id": uuid.UUID(accounts[number % len(accounts)]),
                    "date": date,
                    "amount": amount * 10 if is_income else -amount,
                    "kind": "income" if is_income else "expense",
                    "description": "NOMINA" if is_income else rng.choice(MERCHANTS),
                    "category_id": rng.choice(income if is_income else expense),
                    "tags": ["viaje"] if number % 97 == 0 else [],
                    "source": "import",
                    "pending": False,
                    "created_at": now,
                    "updated_at": now,
                }
            )
        db.execute(insert(Transaction), rows)
        db.commit()


@pytest.mark.slow
def test_every_screen_answers_quickly_with_50000_movements(app: FastAPI, ana: TestClient) -> None:
    accounts = [
        str(new_account(ana, name=name, opening_date="2023-10-01", opening_balance="5000")["id"])
        for name in ("Nómina", "Ahorro", "Tarjeta", "Efectivo")
    ]
    ana.get("/api/categories").raise_for_status()  # creates the default categories
    ana.patch("/api/me/preferences", json={"budget_mode": "limits"}).raise_for_status()
    _load(app, accounts)

    requests = [
        "/api/dashboard",
        "/api/accounts",
        "/api/transactions",
        f"/api/transactions?account_id={accounts[0]}",
        "/api/transactions?q=mercadona",
        "/api/budget",
        "/api/savings-rate",
        "/api/goals",
        "/api/calculators/context",
        "/api/reports/net-worth",
        "/api/reports/net-worth?start=2023-10-01",
        "/api/reports/cash-flow",
        "/api/reports/cash-flow?start=2023-10-01&group=year",
        "/api/reports/spending",
        "/api/reports/spending?by=merchant&start=2026-01-01&end=2026-12-31",
        "/api/reports/spending?by=tag&start=2023-10-01&end=2026-10-15",
    ]
    slow = {}
    for url in requests:
        started = time.perf_counter()
        response = ana.get(url)
        elapsed = time.perf_counter() - started
        assert response.status_code == 200, (url, response.text)
        if elapsed >= LIMIT_SECONDS:
            slow[url] = round(elapsed, 2)
    assert slow == {}

    started = time.perf_counter()
    assert ana.get("/api/export.json").status_code == 200
    assert time.perf_counter() - started < 10  # the whole history, once in a while

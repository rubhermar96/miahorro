"""Everything the user has, to take away (RF-IMP-04): one JSON file, or a ZIP with a CSV per
table that opens in a Spanish spreadsheet. Secrets (password, second factor, passkeys,
sessions, capture tokens) never leave; shared tables (templates, reference values) are not
the user's data.
"""

import csv
import datetime as dt
import io
import json
import uuid
import zipfile
from decimal import Decimal
from typing import Any

from sqlalchemy import Numeric, inspect, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models.accounts import Account, AccountRate
from app.models.budgets import BudgetAssignment
from app.models.calculators import CalculatorScenario
from app.models.capture import CaptureCard, RecurringItem
from app.models.goals import GoalAccount, GoalContribution, SavingsGoal
from app.models.imports import CategoryRule, ImportBatch
from app.models.investments import Investment, InvestmentOperation, InvestmentPrice
from app.models.loans import Loan, LoanPrepayment
from app.models.transactions import Category, Transaction
from app.models.user import User
from app.ownership import owned

FORMAT = "miahorro-export"
VERSION = 1

# Table name in the export → model, in an order that reads well.
OWNED: dict[str, type[Any]] = {
    "accounts": Account,
    "categories": Category,
    "transactions": Transaction,
    "category_rules": CategoryRule,
    "imports": ImportBatch,
    "recurring_items": RecurringItem,
    "capture_cards": CaptureCard,
    "savings_goals": SavingsGoal,
    "goal_contributions": GoalContribution,
    "budget_assignments": BudgetAssignment,
    "loans": Loan,
    "loan_prepayments": LoanPrepayment,
    "investments": Investment,
    "investment_operations": InvestmentOperation,
    "investment_prices": InvestmentPrice,
    "calculator_scenarios": CalculatorScenario,
}

PROFILE = (
    "email",
    "display_name",
    "currency",
    "month_start_day",
    "savings_rate_target",
    "budget_mode",
    "budget_rollover",
    "theme",
    "language",
    "created_at",
)


def _plain(value: Any) -> Any:
    """A JSON-friendly value: exact amounts as text, dates in ISO format."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dt.datetime | dt.date):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def _row(row: Base) -> dict[str, Any]:
    columns = inspect(type(row)).columns
    return {c.key: _plain(getattr(row, c.key)) for c in columns if c.key != "user_id"}


def tables(db: Session, user: User) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for name, model in OWNED.items():
        query = owned(model, user)
        if hasattr(model, "created_at"):
            query = query.order_by(model.created_at)
        result[name] = [_row(row) for row in db.scalars(query)]
    # Tables without an owner of their own: through the account or the goal.
    result["account_rates"] = [
        _row(row)
        for row in db.scalars(
            select(AccountRate)
            .join(Account, Account.id == AccountRate.account_id)
            .where(Account.user_id == user.id)
            .order_by(AccountRate.valid_from)
        )
    ]
    result["goal_accounts"] = [
        _row(row)
        for row in db.scalars(
            select(GoalAccount)
            .join(SavingsGoal, SavingsGoal.id == GoalAccount.goal_id)
            .where(SavingsGoal.user_id == user.id)
        )
    ]
    return result


def as_json(db: Session, user: User, now: dt.datetime) -> dict[str, Any]:
    return {
        "format": FORMAT,
        "version": VERSION,
        "exported_at": now.isoformat(),
        "profile": {name: _plain(getattr(user, name)) for name in PROFILE},
        "tables": tables(db, user),
    }


def _cell(value: Any) -> str:
    """A spreadsheet cell the Spanish way: decimal comma, lists and objects as text."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "sí" if value else "no"
    if isinstance(value, list):
        if all(isinstance(item, str) for item in value):
            return ", ".join(value)
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _decimal_columns(model: type[Any]) -> set[str]:
    return {c.key for c in inspect(model).columns if isinstance(c.type, Numeric)}


LEEME = """Exportación de MiAhorro

Un archivo CSV por tabla, separado por punto y coma, en UTF-8, con coma decimal para que se abra
bien en una hoja de cálculo en español. Las fechas van como AAAA-MM-DD y los identificadores
enlazan unas tablas con otras (por ejemplo, transactions.account_id con accounts.id).

El archivo JSON de la exportación tiene lo mismo con importes exactos con punto decimal: es el
que conviene guardar para volver a leerlo con un programa.
"""


def as_zip(db: Session, user: User, now: dt.datetime) -> bytes:
    data = tables(db, user)
    models: dict[str, type[Any]] = {
        **OWNED,
        "account_rates": AccountRate,
        "goal_accounts": GoalAccount,
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("LEEME.txt", LEEME)
        for name, rows in data.items():
            model = models[name]
            columns = [c.key for c in inspect(model).columns if c.key != "user_id"]
            decimals = _decimal_columns(model)
            text = io.StringIO()
            writer = csv.writer(text, delimiter=";", lineterminator="\r\n")
            writer.writerow(columns)
            for row in rows:
                writer.writerow(
                    [
                        _cell(row[c]).replace(".", ",") if c in decimals else _cell(row[c])
                        for c in columns
                    ]
                )
            archive.writestr(f"{name}.csv", "﻿" + text.getvalue())
        archive.writestr(
            "perfil.json",
            json.dumps(
                {
                    "exported_at": now.isoformat(),
                    **{n: _plain(getattr(user, n)) for n in PROFILE},
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    return buffer.getvalue()

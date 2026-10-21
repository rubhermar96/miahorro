"""Dashboard, reports and export (RF-INF-01, 02, 03, 04, RF-PRE-09, RF-IMP-04)."""

import datetime as dt
import json
from decimal import Decimal

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from app import budgets, clock, export, reports
from app.auth.deps import CurrentUser, DbSession
from app.goals import Period, reserved_by_account
from app.networth import NetWorth, NetWorthBook, month_ends
from app.routers.money_types import Money
from finance.periods import period_of, shift

router = APIRouter(prefix="/api", tags=["reports"])


class NetWorthOut(BaseModel):
    date: dt.date
    accounts: Money = Field(description="Accounts in the main currency")
    investments: Money = Field(description="Investments with a price")
    lent: Money = Field(description="What others owe you")
    debts: Money = Field(description="Capital left on your loans")
    total: Money
    other_currencies: dict[str, Money] = Field(description="Accounts in other currencies")


def _net_worth(value: NetWorth) -> NetWorthOut:
    return NetWorthOut(
        date=value.date,
        accounts=value.accounts,
        investments=value.investments,
        lent=value.lent,
        debts=value.debts,
        total=value.total,
        other_currencies=value.other_currencies,
    )


class PeriodOut(BaseModel):
    start: dt.date
    end: dt.date
    income: Money
    expenses: Money = Field(description="Negative")
    saved: Money
    rate: Decimal | None = Field(description="Percent of income saved; null without income")


def _period(value: Period) -> PeriodOut:
    return PeriodOut(
        start=value.start,
        end=value.end,
        income=value.income,
        expenses=value.expenses,
        saved=value.saved,
        rate=value.rate,
    )


class DashboardOut(BaseModel):
    today: dt.date
    net_worth: NetWorthOut
    previous: NetWorthOut | None = Field(description="At the end of last month, to compare")
    available: Money = Field(description="Everyday money, minus what goals hold in it")
    reserved: Money = Field(description="Set aside for goals")
    month: PeriodOut = Field(description="This financial month so far")
    savings_target: int | None


@router.get("/dashboard")
def dashboard(user: CurrentUser, db: DbSession) -> DashboardOut:
    """How things stand today, at a glance."""
    today = clock.today()
    book = NetWorthBook(db, user, today)
    last_month_end = today.replace(day=1) - dt.timedelta(days=1)
    start = book.start()
    start_day = user.month_start_day
    month_start, _ = period_of(today, start_day)
    (month,) = reports.cash_flow(db, user, month_start, today, "total")
    return DashboardOut(
        today=today,
        net_worth=_net_worth(book.at(today)),
        previous=(
            _net_worth(book.at(last_month_end))
            if start is not None and start <= last_month_end
            else None
        ),
        available=budgets.everyday_cash(db, user, today),
        reserved=sum(reserved_by_account(db, user).values(), Decimal(0)),
        month=_period(month),
        savings_target=user.savings_rate_target,
    )


# --- Net worth over time ----------------------------------------------------------------------


class NetWorthReport(BaseModel):
    start: dt.date | None = Field(description="First date with data; null without any")
    points: list[NetWorthOut] = Field(description="End of each month, and the last date")


@router.get("/reports/net-worth")
def net_worth_report(
    user: CurrentUser,
    db: DbSession,
    start: dt.date | None = None,
    end: dt.date | None = None,
) -> NetWorthReport:
    """Net worth at the end of each month: by default the last twelve, from the first day
    there is data."""
    today = clock.today()
    end = min(end or today, today)
    book = NetWorthBook(db, user, today)
    known = book.start()
    if known is None:
        return NetWorthReport(start=None, points=[])
    first = start or shift(end.replace(day=1), -12, 1)
    first = max(first, known)
    if first > end:
        return NetWorthReport(start=known, points=[])
    return NetWorthReport(
        start=known, points=[_net_worth(book.at(day)) for day in month_ends(first, end)]
    )


# --- Income and expenses ----------------------------------------------------------------------


class CashFlowReport(BaseModel):
    periods: list[PeriodOut]
    total: PeriodOut
    savings_target: int | None


@router.get("/reports/cash-flow")
def cash_flow_report(
    user: CurrentUser,
    db: DbSession,
    start: dt.date | None = None,
    end: dt.date | None = None,
    group: reports.Grouping = "month",
) -> CashFlowReport:
    """Income, expenses and the share saved by financial month, by year or for the whole
    range. By default, the last twelve financial months."""
    today = clock.today()
    end = end or today
    if start is None:
        start = shift(period_of(end, user.month_start_day)[0], -11, user.month_start_day)
    periods = reports.cash_flow(db, user, start, end, group)
    income = sum((p.income for p in periods), Decimal(0))
    expenses = sum((p.expenses for p in periods), Decimal(0))
    return CashFlowReport(
        periods=[_period(p) for p in periods],
        total=_period(Period(start, end, income, expenses)),
        savings_target=user.savings_rate_target,
    )


# --- Spending ---------------------------------------------------------------------------------


class RangeOut(BaseModel):
    start: dt.date
    end: dt.date


class SpendLineOut(BaseModel):
    key: str = Field(description="Category id, merchant or tag")
    label: str
    icon: str | None
    amount: Money = Field(description="Spent in the range, positive")
    previous: Money = Field(description="In the previous period")
    last_year: Money = Field(description="Same dates a year earlier")
    children: list[SpendLineOut] = Field(description="Subcategories")


class SpendingReport(BaseModel):
    by: reports.SpendingBy
    current: RangeOut
    previous: RangeOut
    last_year: RangeOut
    total: Money
    total_previous: Money
    total_last_year: Money
    lines: list[SpendLineOut]


def _line(line: reports.SpendLine) -> SpendLineOut:
    return SpendLineOut(
        key=line.key,
        label=line.label,
        icon=line.icon,
        amount=line.amounts[0],
        previous=line.amounts[1],
        last_year=line.amounts[2],
        children=[_line(child) for child in line.children],
    )


@router.get("/reports/spending")
def spending_report(
    user: CurrentUser,
    db: DbSession,
    start: dt.date | None = None,
    end: dt.date | None = None,
    by: reports.SpendingBy = "category",
) -> SpendingReport:
    """Where the money went, next to the previous period and the same dates a year before. By
    default, this financial month so far."""
    today = clock.today()
    if start is None or end is None:
        start, end = period_of(today, user.month_start_day)
    ranges = reports.comparison_ranges(start, end, today, user.month_start_day)
    lines = reports.spending(db, user, ranges, by)
    # Every expense counts in the totals, though tags overlap and lines may be left out.
    total, total_previous, total_last_year = reports.totals(db, user, ranges)
    return SpendingReport(
        by=by,
        current=RangeOut(start=ranges.current[0], end=ranges.current[1]),
        previous=RangeOut(start=ranges.previous[0], end=ranges.previous[1]),
        last_year=RangeOut(start=ranges.last_year[0], end=ranges.last_year[1]),
        total=total,
        total_previous=total_previous,
        total_last_year=total_last_year,
        lines=[_line(line) for line in lines],
    )


# --- Export -----------------------------------------------------------------------------------


def _filename(extension: str) -> str:
    return f"miahorro-{clock.today():%Y-%m-%d}.{extension}"


@router.get(
    "/export.json",
    response_class=Response,
    responses={200: {"content": {"application/json": {}}, "description": "All your data"}},
)
def export_json(user: CurrentUser, db: DbSession) -> Response:
    """All your data in one JSON file, with exact amounts."""
    body = json.dumps(export.as_json(db, user, clock.now()), ensure_ascii=False, indent=2)
    return Response(
        body,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{_filename("json")}"'},
    )


@router.get(
    "/export.zip",
    response_class=Response,
    responses={200: {"content": {"application/zip": {}}, "description": "A CSV per table"}},
)
def export_zip(user: CurrentUser, db: DbSession) -> Response:
    """All your data as CSV files (one per table) in a ZIP, for a spreadsheet."""
    return Response(
        export.as_zip(db, user, clock.now()),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{_filename("zip")}"'},
    )

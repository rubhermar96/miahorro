"""Calculators (RF-CAL-01, 02, 03, 04, 07, 09, 10), their saved scenarios and the reference
values they use. Results are approximate: they never replace a bank's offer or a tax advisor.
"""

import datetime as dt
import uuid
from decimal import Decimal
from typing import Annotated, Any, Literal, Self

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import AfterValidator, BaseModel, Field, ValidationError, model_validator

from app import calculators, clock, reference
from app.auth.deps import CurrentUser, DbSession
from app.models.calculators import CalculatorScenario, ReferenceValue
from app.ownership import get_owned_or_404, owned
from app.reference_data import REGIONS, TABLES
from app.routers.money_types import Money, Rate
from finance.calculators import car, credit, home, mortgage, savings
from finance.loans import add_months
from finance.money import round_cents
from finance.taxes import Bracket, band_rate

router = APIRouter(prefix="/api", tags=["calculators"])


def _positive(value: Decimal) -> Decimal:
    if value <= 0:
        raise ValueError("Debe ser mayor que cero.")
    return value


def _non_negative(value: Decimal) -> Decimal:
    if value < 0:
        raise ValueError("No puede ser negativo.")
    return value


Positive = Annotated[Money, AfterValidator(_positive)]
Amount = Annotated[Money, AfterValidator(_non_negative)]
Calculator = Literal[
    "compound", "savings_goal", "mortgage", "home", "car", "personal_loan", "emergency"
]
Region = Literal[
    "andalucia",
    "aragon",
    "asturias",
    "baleares",
    "canarias",
    "cantabria",
    "castilla_la_mancha",
    "castilla_y_leon",
    "cataluna",
    "valencia",
    "extremadura",
    "galicia",
    "madrid",
    "murcia",
    "navarra",
    "pais_vasco",
    "la_rioja",
]
Name = Annotated[str, Field(min_length=1, max_length=40)]


class ReferenceOut(BaseModel):
    """A reference value a result used, so the user can see and check it."""

    table: str
    table_label: str
    key: str
    label: str
    value: Decimal
    extra: dict[str, Any] | None
    valid_from: dt.date
    source: str
    note: str | None


def _ref_out(row: ReferenceValue) -> ReferenceOut:
    return ReferenceOut(
        table=row.table_name,
        table_label=TABLES.get(row.table_name, row.table_name),
        key=row.key,
        label=REGIONS.get(row.key, row.key),
        value=row.value,
        extra=row.extra,
        valid_from=row.valid_from,
        source=row.source,
        note=row.note,
    )


def _reference(db: DbSession, table: str, key: str) -> ReferenceValue:
    try:
        return reference.get(db, table, key, clock.today())
    except reference.ReferenceDataError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc


def _scale(row: ReferenceValue) -> list[Bracket]:
    try:
        return reference.brackets(row)
    except reference.ReferenceDataError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc


# --- Compound interest (RF-CAL-01) ------------------------------------------------------------


class CompoundIn(BaseModel):
    initial: Amount = Decimal(0)
    monthly: Amount = Field(default=Decimal(0), description="Contribution at each month's start")
    annual_return: Rate = Field(description="Expected yearly return, TAE")
    years: int = Field(ge=1, le=60)
    inflation: Rate = Decimal(0)
    yearly_increase: Rate = Field(default=Decimal(0), description="Contribution growth a year")
    tax_mode: savings.TaxMode = Field(
        default="end", description="none · yearly (deposits) · end (funds, when sold)"
    )


class CompoundYearOut(BaseModel):
    year: int
    contributed: Money
    gains: Money
    tax: Money
    balance: Money
    real_balance: Money


class CompoundOut(BaseModel):
    years: list[CompoundYearOut]
    contributed: Money
    gains: Money
    tax: Money
    final: Money
    final_real: Money
    references: list[ReferenceOut]


@router.post("/calculators/compound")
def compound(body: CompoundIn, user: CurrentUser, db: DbSession) -> CompoundOut:
    """How savings grow with compound interest, after taxes and in today's money."""
    scale_row = _reference(db, "savings_tax", "general")
    result = savings.compound(
        body.initial,
        body.monthly,
        body.annual_return,
        body.years,
        inflation=body.inflation,
        yearly_increase=body.yearly_increase,
        tax_mode=body.tax_mode,
        brackets=_scale(scale_row),
    )
    return CompoundOut(
        years=[CompoundYearOut(**vars(row)) for row in result.years],
        contributed=result.contributed,
        gains=result.gains,
        tax=result.tax,
        final=result.final,
        final_real=result.final_real,
        references=[_ref_out(scale_row)] if body.tax_mode != "none" else [],
    )


# --- Savings target (RF-CAL-02) ---------------------------------------------------------------


class SavingsGoalIn(BaseModel):
    target: Positive
    initial: Amount = Decimal(0)
    annual_return: Rate = Decimal(0)
    mode: Literal["monthly", "date"] = Field(
        description="monthly: how much a month to get there in `months` · "
        "date: when it is reached saving `monthly`"
    )
    months: int | None = Field(default=None, ge=1, le=savings.MAX_MONTHS)
    monthly: Amount | None = None

    @model_validator(mode="after")
    def _needs(self) -> Self:
        if self.mode == "monthly" and self.months is None:
            raise ValueError("Indica en cuántos meses quieres conseguirlo.")
        if self.mode == "date" and self.monthly is None:
            raise ValueError("Indica cuánto ahorras al mes.")
        return self


class SavingsGoalOut(BaseModel):
    monthly: Money | None = Field(description="Saving a month; null if never reached")
    months: int | None = Field(description="Months to reach it; null if never")
    date: dt.date | None
    contributed: Money | None
    gains: Money | None


@router.post("/calculators/savings-goal")
def savings_goal(body: SavingsGoalIn, user: CurrentUser) -> SavingsGoalOut:
    """How much to save a month to reach a target, or when it is reached."""
    monthly, months = body.monthly, body.months
    if body.mode == "monthly" and months is not None:
        monthly = savings.required_monthly(body.target, body.initial, months, body.annual_return)
    elif monthly is not None:
        months = savings.months_to_target(body.target, body.initial, monthly, body.annual_return)
    if months is None or monthly is None:
        return SavingsGoalOut(monthly=monthly, months=None, date=None, contributed=None, gains=None)
    final = savings.future_value(
        body.initial, monthly, savings.monthly_return(body.annual_return), months
    )
    contributed = body.initial + monthly * months
    return SavingsGoalOut(
        monthly=monthly,
        months=months,
        date=add_months(clock.today(), months),
        contributed=contributed,
        gains=round_cents(max(final - contributed, Decimal(0))),
    )


# --- Emergency fund (RF-CAL-10) ---------------------------------------------------------------


class EmergencyIn(BaseModel):
    essential_monthly: Positive = Field(description="Essential expenses a month")
    months: int = Field(default=6, ge=1, le=24, description="Months the fund should cover")
    current: Amount = Field(default=Decimal(0), description="Money already set aside")
    monthly_saving: Amount = Decimal(0)


class EmergencyOut(BaseModel):
    target: Money
    covered_months: Decimal = Field(description="Months the current fund covers, one decimal")
    missing: Money
    months_to_complete: int | None
    date_complete: dt.date | None


@router.post("/calculators/emergency")
def emergency(body: EmergencyIn, user: CurrentUser) -> EmergencyOut:
    """How many months of essential expenses are covered, and what is missing."""
    fund = savings.emergency_fund(
        body.essential_monthly, body.months, body.current, body.monthly_saving
    )
    return EmergencyOut(
        target=fund.target,
        covered_months=fund.covered_months,
        missing=fund.missing,
        months_to_complete=fund.months_to_complete,
        date_complete=(
            add_months(clock.today(), fund.months_to_complete) if fund.months_to_complete else None
        ),
    )


# --- Mortgage (RF-CAL-03) ---------------------------------------------------------------------


class MortgageOfferIn(BaseModel):
    name: Name
    rate_type: mortgage.RateType = "fixed"
    fixed_rate: Rate = Field(description="TIN, or the rate of the initial period")
    fixed_months: int = Field(default=0, ge=0, le=480, description="Initial period, months")
    spread: Rate = Field(default=Decimal(0), description="Diferencial over the Euribor")
    discount: Rate = Field(default=Decimal(0), description="Points off with linked products")
    linked_yearly_cost: Amount = Field(default=Decimal(0), description="Their cost a year")
    upfront_costs: Amount = Decimal(0)


class MortgageIn(BaseModel):
    principal: Positive
    years: int = Field(ge=1, le=40)
    offers: list[MortgageOfferIn] = Field(min_length=1, max_length=3)
    euribor: list[Rate] = Field(
        min_length=1, max_length=3, description="Scenarios: Euribor from the first review on"
    )


class YearOut(BaseModel):
    year: int
    payment: Money
    interest: Money
    principal: Money
    outstanding: Money


class OutcomeOut(BaseModel):
    first_payment: Money
    later_payment: Money | None = Field(description="After the initial period")
    interest: Money
    linked_cost: Money
    total_cost: Money = Field(description="Interest + linked products + upfront costs")
    years: list[YearOut]


class ScenarioOutcome(BaseModel):
    euribor: Rate
    with_discount: OutcomeOut
    without_discount: OutcomeOut
    discount_saves: Money = Field(description="Positive: the linked products pay off")


class OfferOut(BaseModel):
    name: str
    rate_type: mortgage.RateType
    scenarios: list[ScenarioOutcome]


class MortgageOut(BaseModel):
    offers: list[OfferOut]
    cheapest: list[int] = Field(description="For each scenario, the offer that costs least")


def _outcome_out(result: mortgage.Outcome) -> OutcomeOut:
    return OutcomeOut(
        first_payment=result.first_payment,
        later_payment=result.later_payment,
        interest=result.interest,
        linked_cost=result.linked_cost,
        total_cost=result.total_cost,
        years=[YearOut(**vars(row)) for row in result.years],
    )


@router.post("/calculators/mortgage")
def mortgage_calculator(body: MortgageIn, user: CurrentUser) -> MortgageOut:
    """Compare mortgage offers under several Euribor scenarios, with and without the
    discounts for linked products."""
    months = body.years * 12
    start = add_months(clock.today(), 1)
    offers: list[OfferOut] = []
    best_costs: list[list[Decimal]] = [[] for _ in body.euribor]
    for item in body.offers:
        if item.rate_type != "fixed" and item.fixed_months >= months:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"«{item.name}»: el periodo inicial es más largo que el plazo.",
            )
        offer = mortgage.Offer(
            name=item.name,
            rate_type=item.rate_type,
            fixed_rate=item.fixed_rate,
            fixed_months=item.fixed_months,
            spread=item.spread,
            discount=item.discount,
            linked_yearly_cost=item.linked_yearly_cost,
            upfront_costs=item.upfront_costs,
        )
        scenarios = []
        for index, euribor in enumerate(body.euribor):
            linked = mortgage.outcome(
                body.principal, months, offer, euribor, discounted=True, start=start
            )
            plain = mortgage.outcome(
                body.principal, months, offer, euribor, discounted=False, start=start
            )
            scenarios.append(
                ScenarioOutcome(
                    euribor=euribor,
                    with_discount=_outcome_out(linked),
                    without_discount=_outcome_out(plain),
                    discount_saves=plain.total_cost - linked.total_cost,
                )
            )
            best_costs[index].append(min(linked.total_cost, plain.total_cost))
        offers.append(OfferOut(name=item.name, rate_type=item.rate_type, scenarios=scenarios))
    return MortgageOut(
        offers=offers,
        cheapest=[costs.index(min(costs)) for costs in best_costs],
    )


# --- Home purchase (RF-CAL-04) ----------------------------------------------------------------


class HomeIn(BaseModel):
    price: Positive
    region: Region
    new_build: bool = False
    tax_rate: Rate | None = Field(
        default=None, description="A reduced rate that applies to you (young, large family…)"
    )
    financed_percent: Rate = Field(default=Decimal(80), description="Of the price")
    annual_rate: Rate = Field(default=Decimal(3), description="TIN of the mortgage")
    years: int = Field(default=30, ge=1, le=40)
    notary: Amount | None = Field(default=None, description="Null: the table's estimate")
    registry: Amount | None = None
    gestoria: Amount | None = None
    appraisal: Amount | None = None
    agency_percent: Rate = Decimal(0)
    net_income: Amount = Field(default=Decimal(0), description="Net a month, household")
    other_debts: Amount = Field(default=Decimal(0), description="Other loan payments a month")
    max_ratio: Rate = Field(default=Decimal(35), description="Of net income for debts")
    savings: Amount | None = Field(default=None, description="Money available for the purchase")
    monthly_saving: Amount = Decimal(0)


class HomeOut(BaseModel):
    tax_name: Literal["ITP", "IVA", "IGIC"]
    tax: Money
    ajd: Money
    notary: Money
    registry: Money
    gestoria: Money
    appraisal: Money
    agency: Money
    costs: Money
    total: Money = Field(description="Price plus costs")
    mortgage: Money
    down_payment: Money
    cash_needed: Money = Field(description="Down payment plus costs")
    payment: Money
    debt_ratio: Decimal | None = Field(description="Percent of net income, other debts included")
    max_payment: Money
    max_price: Money | None
    limited_by: Literal["income", "savings"] | None
    months_to_buy: int | None
    buy_date: dt.date | None
    references: list[ReferenceOut]
    warnings: list[str]


@router.post("/calculators/home")
def home_purchase(body: HomeIn, user: CurrentUser, db: DbSession) -> HomeOut:
    """What buying a home costs in taxes and fees, the savings it takes and whether the
    income bears the mortgage."""
    used: list[ReferenceValue] = []
    warnings: list[str] = []
    if body.new_build:
        canarias = body.region == "canarias"
        vat_row = _reference(db, "vat", "new_home_canarias" if canarias else "new_home")
        ajd_row = _reference(db, "ajd", body.region)
        used += [vat_row, ajd_row]
        tax_name: Literal["ITP", "IVA", "IGIC"] = "IGIC" if canarias else "IVA"
        scale, marginal, ajd = _scale(vat_row), reference.is_marginal(vat_row), ajd_row.value
    else:
        itp_row = _reference(db, "itp", body.region)
        used.append(itp_row)
        tax_name, ajd = "ITP", Decimal(0)
        scale, marginal = _scale(itp_row), reference.is_marginal(itp_row)
    if body.tax_rate is not None:
        scale, marginal = [Bracket(None, body.tax_rate)], True

    costs = reference.in_force(db, "home_costs", clock.today())

    def fee(given: Decimal | None, key: str) -> Decimal:
        if given is not None:
            return given
        row = costs.get(key)
        if row is None:
            return Decimal(0)
        if row not in used:
            used.append(row)
        return row.value

    fees = home.Fees(
        notary=fee(body.notary, "notary"),
        registry=fee(body.registry, "registry"),
        gestoria=fee(body.gestoria, "gestoria"),
        appraisal=fee(body.appraisal, "appraisal"),
        agency_percent=body.agency_percent,
    )
    tax = home.PurchaseTax(scale, marginal=marginal, ajd=ajd)
    bought = home.purchase(body.price, tax, fees, body.financed_percent)
    afford = home.affordability(
        body.price,
        tax,
        fees,
        body.financed_percent,
        annual_rate=body.annual_rate,
        months=body.years * 12,
        net_income=body.net_income,
        other_debts=body.other_debts,
        max_ratio=body.max_ratio,
        savings=body.savings,
        monthly_saving=body.monthly_saving,
    )
    if body.financed_percent > 80:
        warnings.append(
            "Los bancos suelen financiar como mucho el 80 % del precio o de la tasación (el "
            "menor) en primera vivienda; más solo con avales o programas especiales."
        )
    if afford.debt_ratio is not None and afford.debt_ratio > body.max_ratio:
        warnings.append(
            f"Las deudas se llevarían el {afford.debt_ratio} % de tus ingresos: más del "
            f"{body.max_ratio.normalize()} % que suelen aceptar los bancos."
        )
    return HomeOut(
        tax_name=tax_name,
        tax=bought.tax,
        ajd=bought.ajd,
        notary=bought.notary,
        registry=bought.registry,
        gestoria=bought.gestoria,
        appraisal=bought.appraisal,
        agency=bought.agency,
        costs=bought.costs,
        total=body.price + bought.costs,
        mortgage=bought.mortgage,
        down_payment=bought.down_payment,
        cash_needed=bought.cash_needed,
        payment=afford.payment,
        debt_ratio=afford.debt_ratio,
        max_payment=afford.max_payment,
        max_price=afford.max_price,
        limited_by=afford.limited_by,
        months_to_buy=afford.months_to_buy,
        buy_date=(
            add_months(clock.today(), afford.months_to_buy)
            if afford.months_to_buy is not None
            else None
        ),
        references=[_ref_out(row) for row in used],
        warnings=warnings,
    )


# --- Car (RF-CAL-07) --------------------------------------------------------------------------


class CarOptionIn(BaseModel):
    kind: car.OptionKind
    name: Name
    down_payment: Amount = Field(default=Decimal(0), description="Entrada; renting: initial")
    rate: Rate = Field(default=Decimal(0), description="TIN")
    months: int = Field(default=0, ge=0, le=120)
    opening_fee_percent: Rate = Decimal(0)
    final_payment: Amount = Field(default=Decimal(0), description="PCP: cuota final")
    keep: bool = Field(default=True, description="PCP: pay the final instalment and keep it")
    monthly_fee: Amount = Field(default=Decimal(0), description="Renting fee a month")

    @model_validator(mode="after")
    def _complete(self) -> Self:
        if self.kind != "cash" and self.months < 1:
            raise ValueError(f"«{self.name}»: indica el plazo en meses.")
        if self.kind == "renting" and self.monthly_fee <= 0:
            raise ValueError(f"«{self.name}»: indica la cuota del renting.")
        return self


class CarIn(BaseModel):
    price: Positive = Field(description="Price with VAT")
    co2: int = Field(ge=0, le=999, description="WLTP emissions, g/km")
    registration_included: bool = Field(
        default=True, description="The price already includes the registration tax"
    )
    years: int = Field(ge=1, le=25, description="Years you will use the car")
    km_per_year: int = Field(ge=0, le=200000)
    consumption: Rate = Field(description="Litres or kWh per 100 km")
    energy_price: Rate = Field(description="€ per litre or kWh")
    insurance: Amount = Decimal(0)
    road_tax: Amount = Field(default=Decimal(0), description="IVTM a year")
    maintenance: Amount = Field(default=Decimal(0), description="A year")
    itv_cost: Amount = Decimal(45)
    resale_value: Amount | None = Field(default=None, description="Null: estimated")
    options: list[CarOptionIn] = Field(min_length=1, max_length=4)


class RunningOut(BaseModel):
    energy: Money
    insurance: Money
    road_tax: Money
    maintenance: Money
    itv: Money
    total: Money


class CarOutcomeOut(BaseModel):
    name: str
    kind: car.OptionKind
    months: int = Field(description="Time the costs cover")
    upfront: Money
    monthly: Money
    final_payment: Money
    financing: Money = Field(description="Interest and fees")
    running: RunningOut
    resale: Money
    total: Money = Field(description="Net cost over `months`")
    per_year: Money
    per_km: Decimal | None
    apr: Decimal | None = Field(description="TAE")


class CarOut(BaseModel):
    registration: Money = Field(description="Registration tax of this car")
    registration_rate: Decimal
    resale_estimated: bool
    options: list[CarOutcomeOut]
    cheapest: int = Field(description="Option with the lowest cost a year")
    references: list[ReferenceOut]


@router.post("/calculators/car")
def car_calculator(body: CarIn, user: CurrentUser, db: DbSession) -> CarOut:
    """Total cost of owning a car, per year and per km, for each way of paying for it."""
    reg_row = _reference(db, "car_registration", "general")
    scale = _scale(reg_row)
    tax = car.registration_tax(body.price, body.co2, scale)
    running = car.Running(
        km_per_year=body.km_per_year,
        consumption=body.consumption,
        energy_price=body.energy_price,
        insurance=body.insurance,
        road_tax=body.road_tax,
        maintenance=body.maintenance,
        itv_cost=body.itv_cost,
    )
    results = []
    for item in body.options:
        option = car.CarOption(**item.model_dump())
        acquisition = body.price + (Decimal(0) if body.registration_included else tax)
        if item.kind == "pcp" and item.final_payment >= acquisition - item.down_payment:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"«{item.name}»: la cuota final no puede ser mayor que lo financiado.",
            )
        outcome = car.cost_option(
            option,
            price=body.price,
            registration=Decimal(0) if body.registration_included else tax,
            years=body.years,
            running=running,
            resale=body.resale_value,
        )
        results.append(
            CarOutcomeOut(
                name=outcome.name,
                kind=outcome.kind,
                months=outcome.months,
                upfront=outcome.upfront,
                monthly=outcome.monthly,
                final_payment=outcome.final_payment,
                financing=outcome.financing,
                running=RunningOut(**vars(outcome.running), total=outcome.running.total),
                resale=outcome.resale,
                total=outcome.total,
                per_year=outcome.per_year,
                per_km=outcome.per_km,
                apr=outcome.apr,
            )
        )
    per_year = [r.per_year for r in results]
    return CarOut(
        registration=tax,
        registration_rate=band_rate(Decimal(body.co2), scale),
        resale_estimated=body.resale_value is None,
        options=results,
        cheapest=per_year.index(min(per_year)),
        references=[_ref_out(reg_row)],
    )


# --- Personal loan (RF-CAL-09) ----------------------------------------------------------------


class LoanOfferIn(BaseModel):
    name: Name
    amount: Positive
    tin: Rate
    months: int = Field(ge=1, le=120)
    opening_fee_percent: Rate = Decimal(0)
    upfront_costs: Amount = Field(default=Decimal(0), description="Other costs at the start")
    monthly_costs: Amount = Field(default=Decimal(0), description="Linked insurance and the like")


class PersonalLoanIn(BaseModel):
    offers: list[LoanOfferIn] = Field(min_length=1, max_length=3)


class LoanOfferOut(BaseModel):
    name: str
    payment: Money
    monthly_total: Money
    interest: Money
    fees: Money
    extras: Money
    total_cost: Money
    total_paid: Money
    apr: Decimal | None = Field(description="TAE with the official formula")


class PersonalLoanOut(BaseModel):
    offers: list[LoanOfferOut]
    cheapest: int = Field(description="Offer with the lowest total cost")


@router.post("/calculators/personal-loan")
def personal_loan(body: PersonalLoanIn, user: CurrentUser) -> PersonalLoanOut:
    """Instalment, real TAE and total cost of loan offers, side by side."""
    offers = []
    for item in body.offers:
        loan = credit.personal_loan(
            item.amount,
            item.tin,
            item.months,
            opening_fee_percent=item.opening_fee_percent,
            upfront_costs=item.upfront_costs,
            monthly_costs=item.monthly_costs,
        )
        offers.append(LoanOfferOut(name=item.name, **vars(loan)))
    costs = [o.total_cost for o in offers]
    return PersonalLoanOut(offers=offers, cheapest=costs.index(min(costs)))


# --- Your data, to prefill ---------------------------------------------------------------------


class CategorySpend(BaseModel):
    category_id: uuid.UUID | None = Field(description="Null: uncategorised")
    name: str
    icon: str | None
    monthly: Money = Field(description="Average spent a month, positive")


class EuriborOut(BaseModel):
    month: dt.date
    value: Rate


class ContextOut(BaseModel):
    months: int = Field(description="Complete financial months with movements averaged")
    start: dt.date | None
    end: dt.date | None
    income: Money = Field(description="Average a month")
    expenses: Money = Field(description="Average a month, positive")
    saved: Money = Field(description="Average a month")
    liquidity: Money = Field(description="Everyday accounts, minus what goals hold")
    loan_payments: Money = Field(description="Next instalment of each loan owed, added up")
    categories: list[CategorySpend] = Field(description="Top-level expense categories")
    euribor: EuriborOut | None


@router.get("/calculators/context")
def context(user: CurrentUser, db: DbSession) -> ContextOut:
    """Averages of the last three complete financial months, to prefill the calculators."""
    data = calculators.context(db, user, clock.today())
    return ContextOut(
        months=data.months,
        start=data.start,
        end=data.end,
        income=data.income,
        expenses=data.expenses,
        saved=data.income - data.expenses,
        liquidity=data.liquidity,
        loan_payments=data.loan_payments,
        categories=[
            CategorySpend(category_id=c.id, name=c.name, icon=c.icon, monthly=c.monthly)
            for c in data.categories
        ],
        euribor=EuriborOut(month=data.euribor[0], value=data.euribor[1]) if data.euribor else None,
    )


@router.get("/calculators/references")
def references(
    user: CurrentUser,
    db: DbSession,
    table: Annotated[list[str] | None, Query(description="Only these tables")] = None,
) -> list[ReferenceOut]:
    """Reference values in force today, with their date and source."""
    today = clock.today()
    rows = []
    for name in table or list(TABLES):
        rows += sorted(
            reference.in_force(db, name, today).values(),
            key=lambda row: REGIONS.get(row.key, row.key),
        )
    return [_ref_out(row) for row in rows]


# --- Saved scenarios --------------------------------------------------------------------------

INPUTS: dict[str, type[BaseModel]] = {
    "compound": CompoundIn,
    "savings_goal": SavingsGoalIn,
    "mortgage": MortgageIn,
    "home": HomeIn,
    "car": CarIn,
    "personal_loan": PersonalLoanIn,
    "emergency": EmergencyIn,
}


class ScenarioIn(BaseModel):
    calculator: Calculator
    name: Annotated[str, Field(min_length=1, max_length=60)]
    inputs: dict[str, Any] = Field(description="The calculator's request body")


class ScenarioUpdate(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=60)] | None = None
    inputs: dict[str, Any] | None = None


class ScenarioOut(BaseModel):
    id: uuid.UUID
    calculator: Calculator
    name: str
    inputs: dict[str, Any]
    created_at: dt.datetime
    updated_at: dt.datetime


def _checked_inputs(calculator: str, inputs: dict[str, Any]) -> dict[str, Any]:
    """Store only what the calculator accepts, so a saved scenario can always be run."""
    try:
        return INPUTS[calculator].model_validate(inputs).model_dump(mode="json")
    except ValidationError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Los datos del escenario no son válidos para esta calculadora.",
        ) from exc


def _tidy(name: str) -> str:
    name = " ".join(name.split())
    if not name:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Ponle un nombre al escenario.")
    return name


def _scenario_out(row: CalculatorScenario) -> ScenarioOut:
    return ScenarioOut(
        id=row.id,
        calculator=row.calculator,
        name=row.name,
        inputs=row.inputs,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/scenarios")
def list_scenarios(
    user: CurrentUser, db: DbSession, calculator: Calculator | None = None
) -> list[ScenarioOut]:
    query = owned(CalculatorScenario, user).order_by(CalculatorScenario.updated_at.desc())
    if calculator:
        query = query.where(CalculatorScenario.calculator == calculator)
    return [_scenario_out(row) for row in db.scalars(query)]


@router.post("/scenarios", status_code=status.HTTP_201_CREATED)
def create_scenario(body: ScenarioIn, user: CurrentUser, db: DbSession) -> ScenarioOut:
    row = CalculatorScenario(
        user_id=user.id,
        calculator=body.calculator,
        name=_tidy(body.name),
        inputs=_checked_inputs(body.calculator, body.inputs),
        created_at=clock.now(),
        updated_at=clock.now(),
    )
    db.add(row)
    db.commit()
    return _scenario_out(row)


@router.patch("/scenarios/{scenario_id}")
def update_scenario(
    scenario_id: uuid.UUID, body: ScenarioUpdate, user: CurrentUser, db: DbSession
) -> ScenarioOut:
    row = get_owned_or_404(db, CalculatorScenario, scenario_id, user)
    if body.name is not None:
        row.name = _tidy(body.name)
    if body.inputs is not None:
        row.inputs = _checked_inputs(row.calculator, body.inputs)
    row.updated_at = clock.now()
    db.commit()
    return _scenario_out(row)


@router.delete("/scenarios/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scenario(scenario_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Response:
    db.delete(get_owned_or_404(db, CalculatorScenario, scenario_id, user))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

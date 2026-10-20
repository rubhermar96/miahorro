"""Calculators (RF-CAL-01, 02, 03, 04, 07, 09, 10), saved scenarios and reference tables
(RF-PLT-02). Today is 15/10/2026 (fake clock)."""

import datetime as dt
import typing
from decimal import Decimal
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import reference
from app.models.calculators import CALCULATORS, ReferenceValue
from app.reference_data import REGIONS, SEED, TABLES
from app.routers.calculators import INPUTS, Calculator, Region
from tests.test_accounts import new_account
from tests.test_loans import new_loan
from tests.test_transactions import add, category_id


@pytest.fixture
def tables(app: FastAPI) -> None:
    with app.state.session_factory() as db:
        reference.sync(db)


def calc(client: TestClient, name: str, **body: Any) -> Any:
    response = client.post(f"/api/calculators/{name}", json=body)
    assert response.status_code == 200, response.text
    return response.json()


# --- Reference tables -------------------------------------------------------------------------


def test_every_reference_value_has_a_date_and_a_source() -> None:
    assert SEED
    for seed in SEED:
        assert seed.table in TABLES
        assert seed.source.strip()
        assert isinstance(seed.valid_from, dt.date)
        assert seed.amount >= 0


def test_itp_and_ajd_cover_every_region() -> None:
    for table in ("itp", "ajd"):
        assert {s.key for s in SEED if s.table == table} == set(REGIONS)
    assert set(typing.get_args(Region)) == set(REGIONS)
    assert set(typing.get_args(Calculator)) == set(CALCULATORS) == set(INPUTS)


def test_every_scale_reads_and_ends_open(app: FastAPI, tables: None) -> None:
    with app.state.session_factory() as db:
        for row in db.scalars(select(ReferenceValue)):
            scale = reference.brackets(row)
            assert scale[-1].up_to is None
            limits = [b.up_to for b in scale[:-1]]
            assert limits == sorted(limits)  # type: ignore[type-var]


def test_sync_adds_what_is_missing_and_keeps_edits(app: FastAPI) -> None:
    with app.state.session_factory() as db:
        assert reference.sync(db) == len(SEED)
        row = reference.get(db, "itp", "madrid", dt.date(2026, 10, 15))
        row.value = Decimal("5.5")
        db.commit()

        assert reference.sync(db) == 0
        assert reference.get(db, "itp", "madrid", dt.date(2026, 10, 15)).value == Decimal("5.5")


def test_the_value_in_force_is_the_latest_one_that_has_started(app: FastAPI, tables: None) -> None:
    with app.state.session_factory() as db:
        db.add(
            ReferenceValue(
                table_name="itp",
                key="madrid",
                value=Decimal(5),
                valid_from=dt.date(2027, 1, 1),
                source="Prueba",
            )
        )
        db.commit()

        assert reference.get(db, "itp", "madrid", dt.date(2026, 12, 31)).value == 6
        assert reference.get(db, "itp", "madrid", dt.date(2027, 1, 1)).value == 5
        with pytest.raises(reference.ReferenceDataError):
            reference.get(db, "itp", "madrid", dt.date(2025, 12, 31))


def test_a_badly_written_scale_is_reported(app: FastAPI, ana: TestClient, tables: None) -> None:
    with app.state.session_factory() as db:
        row = reference.get(db, "itp", "baleares", dt.date(2026, 10, 15))
        row.extra = {"brackets": [{"rate": "8"}]}
        db.commit()

    response = ana.post("/api/calculators/home", json={"price": "300000", "region": "baleares"})

    assert response.status_code == 503
    assert "mal escrita" in response.json()["error"]["message"]


def test_references_endpoint_shows_sources(ana: TestClient, tables: None) -> None:
    rows = ana.get("/api/calculators/references", params={"table": "itp"}).json()

    assert len(rows) == len(REGIONS)
    madrid = next(r for r in rows if r["key"] == "madrid")
    assert madrid["label"] == "Comunidad de Madrid"
    assert madrid["value"] == "6.0000"
    assert "guiafiscal.es" in madrid["source"]
    assert madrid["valid_from"] == "2026-01-01"


def test_missing_tables_give_a_clear_error(ana: TestClient) -> None:
    response = ana.post("/api/calculators/home", json={"price": "200000", "region": "madrid"})

    assert response.status_code == 503
    assert "/admin" in response.json()["error"]["message"]


# --- Compound interest, savings target and emergency fund -------------------------------------


def test_compound_interest_with_taxes_at_the_end(ana: TestClient, tables: None) -> None:
    result = calc(ana, "compound", initial="10000", annual_return="5", years=10, inflation="2")

    assert result["final"] == "15088.27"
    assert result["tax"] == "1200.68"
    assert len(result["years"]) == 10
    assert result["years"][0]["balance"] == "10500.00"
    assert result["references"][0]["table"] == "savings_tax"


def test_compound_interest_without_taxes(ana: TestClient, tables: None) -> None:
    result = calc(ana, "compound", initial="10000", annual_return="5", years=10, tax_mode="none")

    assert (result["final"], result["tax"], result["references"]) == ("16288.95", "0.00", [])


def test_savings_goal_monthly_amount(ana: TestClient) -> None:
    result = calc(ana, "savings-goal", target="12000", mode="monthly", months=24)

    assert result["monthly"] == "500.00"
    assert result["date"] == "2028-10-15"
    assert result["contributed"] == "12000.00"


def test_savings_goal_date_at_a_pace(ana: TestClient) -> None:
    result = calc(ana, "savings-goal", target="1000", mode="date", monthly="100")

    assert (result["months"], result["date"]) == (10, "2027-08-15")
    never = calc(ana, "savings-goal", target="1000", mode="date", monthly="0")
    assert (never["months"], never["date"]) == (None, None)


def test_savings_goal_needs_its_inputs(ana: TestClient) -> None:
    response = ana.post("/api/calculators/savings-goal", json={"target": "1000", "mode": "monthly"})

    assert response.status_code == 422


def test_emergency_fund(ana: TestClient) -> None:
    result = calc(
        ana,
        "emergency",
        essential_monthly="1500",
        months=6,
        current="4000",
        monthly_saving="500",
    )

    assert result["target"] == "9000.00"
    assert result["covered_months"] == "2.7"
    assert result["missing"] == "5000.00"
    assert (result["months_to_complete"], result["date_complete"]) == (10, "2027-08-15")


# --- Mortgage ---------------------------------------------------------------------------------


def test_mortgage_offers_under_euribor_scenarios(ana: TestClient) -> None:
    result = calc(
        ana,
        "mortgage",
        principal="150000",
        years=30,
        euribor=["2", "4"],
        offers=[
            {"name": "Fija", "fixed_rate": "3", "discount": "0.5", "linked_yearly_cost": "200"},
            {
                "name": "Mixta",
                "rate_type": "mixed",
                "fixed_rate": "2",
                "fixed_months": 60,
                "spread": "0.6",
            },
        ],
    )

    fixed, mixed = result["offers"]
    # =PAGO(3%/12; 360; -150000) and, with the discount, =PAGO(2,5%/12; 360; -150000)
    assert fixed["scenarios"][0]["without_discount"]["first_payment"] == "632.41"
    assert fixed["scenarios"][0]["with_discount"]["first_payment"] == "592.68"
    assert fixed["scenarios"][0]["with_discount"]["linked_cost"] == "6000.00"
    assert Decimal(fixed["scenarios"][0]["discount_saves"]) > 0
    # The fixed offer does not care about the Euribor; the mixed one does.
    assert fixed["scenarios"][0]["with_discount"] == fixed["scenarios"][1]["with_discount"]
    low, high = (s["without_discount"] for s in mixed["scenarios"])
    assert Decimal(high["later_payment"]) > Decimal(low["later_payment"])
    assert result["cheapest"] == [1, 0]
    assert len(fixed["scenarios"][0]["with_discount"]["years"]) == 30


def test_initial_period_longer_than_the_term(ana: TestClient) -> None:
    response = ana.post(
        "/api/calculators/mortgage",
        json={
            "principal": "100000",
            "years": 5,
            "euribor": ["2"],
            "offers": [
                {"name": "Mixta", "rate_type": "mixed", "fixed_rate": "2", "fixed_months": 60}
            ],
        },
    )

    assert response.status_code == 422


# --- Home purchase ----------------------------------------------------------------------------


def test_second_hand_home_in_madrid(ana: TestClient, tables: None) -> None:
    result = calc(
        ana,
        "home",
        price="200000",
        region="madrid",
        annual_rate="3",
        net_income="3000",
        savings="60000",
        monthly_saving="800",
    )

    assert (result["tax_name"], result["tax"], result["ajd"]) == ("ITP", "12000.00", "0.00")
    # Table estimates: notary 600, registry 400, gestoría 350, appraisal 400
    assert result["costs"] == "13750.00"
    assert result["cash_needed"] == "53750.00"
    assert result["mortgage"] == "160000.00"
    assert result["payment"] == "674.57"  # =PAGO(3%/12; 360; -160000)
    assert result["debt_ratio"] == "22.5"
    assert result["months_to_buy"] == 0
    # 20 % down + 6 % ITP + 1.750 € of costs must fit in the 60.000 € saved
    assert (result["limited_by"], result["max_price"]) == ("savings", "224038.00")
    used = {(r["table"], r["key"]) for r in result["references"]}
    assert ("itp", "madrid") in used
    assert ("home_costs", "notary") in used
    assert result["warnings"] == []


def test_new_home_pays_vat_and_ajd(ana: TestClient, tables: None) -> None:
    result = calc(ana, "home", price="200000", region="andalucia", new_build=True)

    assert (result["tax_name"], result["tax"], result["ajd"]) == ("IVA", "20000.00", "2400.00")


def test_new_home_in_canarias_pays_igic(ana: TestClient, tables: None) -> None:
    cheap = calc(ana, "home", price="150000", region="canarias", new_build=True)
    dear = calc(ana, "home", price="250000", region="canarias", new_build=True)

    assert (cheap["tax_name"], cheap["tax"], cheap["ajd"]) == ("IGIC", "4500.00", "1125.00")
    assert dear["tax"] == "17500.00"


def test_progressive_itp_and_a_reduced_rate(ana: TestClient, tables: None) -> None:
    catalan = calc(ana, "home", price="700000", region="cataluna", financed_percent="0")
    reduced = calc(ana, "home", price="200000", region="madrid", tax_rate="4")

    assert catalan["tax"] == "71000.00"  # 10 % up to 600.000 and 11 % above
    assert reduced["tax"] == "8000.00"


def test_own_costs_replace_the_estimates(ana: TestClient, tables: None) -> None:
    result = calc(
        ana,
        "home",
        price="100000",
        region="madrid",
        notary="900",
        registry="500",
        gestoria="0",
        appraisal="300",
        agency_percent="3",
    )

    assert (result["notary"], result["gestoria"], result["agency"]) == ("900.00", "0.00", "3000.00")
    assert {r["table"] for r in result["references"]} == {"itp"}


def test_home_warnings(ana: TestClient, tables: None) -> None:
    result = calc(
        ana, "home", price="300000", region="madrid", financed_percent="90", net_income="2000"
    )

    assert len(result["warnings"]) == 2
    assert Decimal(result["debt_ratio"]) > 35
    assert result["max_price"] is not None


# --- Car --------------------------------------------------------------------------------------

CAR = {
    "price": "24200",
    "co2": 130,
    "years": 5,
    "km_per_year": 15000,
    "consumption": "6",
    "energy_price": "1.6",
    "insurance": "500",
    "road_tax": "100",
    "maintenance": "300",
    "resale_value": "9000",
}


def test_car_options_side_by_side(ana: TestClient, tables: None) -> None:
    result = calc(
        ana,
        "car",
        **CAR,
        registration_included=False,
        options=[
            {"kind": "cash", "name": "Contado"},
            {"kind": "loan", "name": "Préstamo", "down_payment": "5000", "rate": "7", "months": 60},
            {"kind": "renting", "name": "Renting", "monthly_fee": "450", "months": 48},
        ],
    )

    assert result["registration"] == "950.00"  # 4,75 % of 20.000 € without VAT
    assert result["registration_rate"] == "4.75"
    cash, loan, renting = result["options"]
    assert cash["upfront"] == "25150.00"
    assert cash["running"]["total"] == "11745.00"
    assert cash["total"] == "27895.00"  # 25.150 + 11.745 - 9.000 of resale
    assert Decimal(loan["total"]) > Decimal(cash["total"])
    assert loan["apr"] is not None
    assert renting["months"] == 48
    assert renting["running"]["insurance"] == "0.00"
    assert result["cheapest"] == 0
    assert result["resale_estimated"] is False


def test_car_option_checks(ana: TestClient, tables: None) -> None:
    no_fee = ana.post(
        "/api/calculators/car",
        json={**CAR, "options": [{"kind": "renting", "name": "Renting", "months": 48}]},
    )
    too_big = ana.post(
        "/api/calculators/car",
        json={
            **CAR,
            "options": [
                {
                    "kind": "pcp",
                    "name": "PCP",
                    "months": 36,
                    "down_payment": "20000",
                    "final_payment": "9000",
                }
            ],
        },
    )

    assert no_fee.status_code == 422
    assert too_big.status_code == 422


# --- Personal loan ----------------------------------------------------------------------------


def test_personal_loan_offers(ana: TestClient) -> None:
    result = calc(
        ana,
        "personal-loan",
        offers=[
            {"name": "Banco A", "amount": "10000", "tin": "7", "months": 60},
            {
                "name": "Banco B",
                "amount": "10000",
                "tin": "6",
                "months": 60,
                "opening_fee_percent": "2",
                "monthly_costs": "15",
            },
        ],
    )

    first, second = result["offers"]
    assert (first["payment"], first["apr"]) == ("198.01", "7.23")
    assert Decimal(second["apr"]) > Decimal(first["apr"])  # the "cheaper" TIN costs more
    assert result["cheapest"] == 0


# --- Your data --------------------------------------------------------------------------------


def test_context_averages_the_last_complete_months(ana: TestClient) -> None:
    account = str(new_account(ana, opening_date="2026-01-01", opening_balance="5000")["id"])
    food = category_id(ana, "Supermercado")
    for month in ("07", "08", "09"):
        add(ana, account, "income", "2000", date=f"2026-{month}-01")
        add(ana, account, "expense", "300", date=f"2026-{month}-05", category_id=food)
    add(ana, account, "expense", "150", date="2026-09-20", category_id=category_id(ana, "Ocio"))
    add(ana, account, "expense", "30", date="2026-08-20")
    add(ana, account, "expense", "999", date="2026-10-02")  # this month is not over
    new_loan(ana)
    ana.put("/api/reference-rates", json={"month": "2026-09-01", "value": "2.17"})

    result = ana.get("/api/calculators/context").json()

    assert (result["months"], result["start"], result["end"]) == (3, "2026-07-01", "2026-09-30")
    assert (result["income"], result["expenses"], result["saved"]) == (
        "2000.00",
        "360.00",
        "1640.00",
    )
    assert [(c["name"], c["monthly"]) for c in result["categories"]] == [
        ("Alimentación", "300.00"),
        ("Ocio", "50.00"),
        ("Sin categoría", "10.00"),
    ]
    assert result["liquidity"] == "8921.00"
    assert result["loan_payments"] == "281.82"
    assert result["euribor"] == {"month": "2026-09-01", "value": "2.1700"}


def test_context_of_a_new_user(ana: TestClient) -> None:
    result = ana.get("/api/calculators/context").json()

    assert (result["months"], result["income"], result["categories"]) == (0, "0.00", [])
    assert result["euribor"] is None


# --- Saved scenarios --------------------------------------------------------------------------


def test_save_compare_and_remove_scenarios(ana: TestClient, bea: TestClient) -> None:
    body = {"target": "1000", "mode": "date", "monthly": "100"}
    created = ana.post(
        "/api/scenarios",
        json={"calculator": "savings_goal", "name": "  Viaje   a Japón ", "inputs": body},
    )
    assert created.status_code == 201, created.text
    scenario = created.json()
    assert scenario["name"] == "Viaje a Japón"
    assert scenario["inputs"]["target"] == "1000.00"  # stored as the calculator reads it
    ana.post(
        "/api/scenarios",
        json={"calculator": "emergency", "name": "Fondo", "inputs": {"essential_monthly": "900"}},
    ).raise_for_status()

    listed = ana.get("/api/scenarios", params={"calculator": "savings_goal"}).json()
    assert [s["name"] for s in listed] == ["Viaje a Japón"]
    assert len(ana.get("/api/scenarios").json()) == 2

    updated = ana.patch(
        f"/api/scenarios/{scenario['id']}",
        json={"name": "Japón", "inputs": {**body, "monthly": "200"}},
    ).json()
    assert (updated["name"], updated["inputs"]["monthly"]) == ("Japón", "200.00")

    assert bea.get("/api/scenarios").json() == []
    assert bea.delete(f"/api/scenarios/{scenario['id']}").status_code == 404
    assert ana.delete(f"/api/scenarios/{scenario['id']}").status_code == 204
    assert len(ana.get("/api/scenarios").json()) == 1


def test_a_scenario_must_be_runnable(ana: TestClient) -> None:
    response = ana.post(
        "/api/scenarios",
        json={"calculator": "home", "name": "Piso", "inputs": {"price": "-5"}},
    )
    blank = ana.post(
        "/api/scenarios",
        json={"calculator": "emergency", "name": "   ", "inputs": {"essential_monthly": "900"}},
    )

    assert response.status_code == 422
    assert blank.status_code == 422

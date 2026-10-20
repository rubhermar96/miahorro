"""Loans and mortgages (RF-PRE-01, 02, 03, 05, 07, 09). Today is 15/10/2026 (fake clock)."""

from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient


def new_loan(client: TestClient, **fields: Any) -> Any:
    body = {
        "name": "Coche",
        "kind": "car",
        "principal": "12000",
        "signed_on": "2026-01-10",
        "first_payment": "2026-02-05",
        "term_months": 48,
        "fixed_rate": "6",
        **fields,
    }
    response = client.post("/api/loans", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def schedule(client: TestClient, loan: Any) -> list[Any]:
    return list(client.get(f"/api/loans/{loan['id']}/schedule").json())


def test_a_fixed_loan_and_where_it_stands_today(ana: TestClient) -> None:
    loan = new_loan(ana)
    rows = schedule(ana, loan)

    assert len(rows) == 48
    assert rows[0]["payment"] == "281.82"  # =PAGO(6%/12; 48; -12000)
    paid = [r for r in rows if r["paid"]]
    assert len(paid) == 9  # February to October
    assert loan["outstanding"] == paid[-1]["outstanding"]
    assert loan["next_payment"] == {"date": "2026-11-05", "amount": "281.82"}
    assert loan["end_date"] == "2030-01-05"
    assert loan["payments_left"] == 39
    assert Decimal(loan["principal_paid"]) + Decimal(loan["outstanding"]) == Decimal(12000)
    total_interest = sum(Decimal(r["interest"]) for r in rows)
    assert Decimal(loan["interest_paid"]) + Decimal(loan["interest_left"]) == total_interest
    assert loan["direction"] == "owe"


def test_variable_rate_follows_euribor_at_each_review(ana: TestClient) -> None:
    for month, value in (("2026-12-01", "2.20"), ("2027-12-15", "2.70")):
        ana.put("/api/reference-rates", json={"month": month, "value": value}).raise_for_status()
    loan = new_loan(
        ana,
        name="Hipoteca",
        kind="mortgage",
        principal="150000",
        term_months=300,
        first_payment="2026-02-05",
        rate_type="variable",
        fixed_rate="1.99",
        fixed_months=12,
        index="euribor_12m",
        spread="0.75",
    )

    rows = schedule(ana, loan)

    assert {r["rate"] for r in rows[:12]} == {"1.9900"}
    assert (rows[12]["rate"], rows[12]["review"]) == ("2.9500", True)  # 2,20 + 0,75
    assert rows[24]["rate"] == "3.4500"  # 2,70 + 0,75, from December 2027
    assert rows[12]["payment"] != rows[11]["payment"]
    assert rows[-1]["outstanding"] == "0.00"


def test_a_review_without_euribor_keeps_the_rate_and_warns(
    ana: TestClient, fake_clock: Any
) -> None:
    loan = new_loan(
        ana,
        kind="mortgage",
        rate_type="mixed",
        fixed_rate="2",
        fixed_months=6,
        index="euribor_12m",
        spread="1",
    )

    assert loan["warnings"] == [
        "Falta el Euribor para la revisión del 05/08/2026: se mantiene el tipo anterior."
    ]
    assert schedule(ana, loan)[6]["rate"] == "2.0000"


def test_simulate_an_early_repayment(ana: TestClient) -> None:
    loan = new_loan(ana, early_repayment_fee="1")

    term = ana.post(
        f"/api/loans/{loan['id']}/simulate",
        json={"date": "2026-10-20", "amount": "3000", "mode": "reduce_term"},
    ).json()
    payment = ana.post(
        f"/api/loans/{loan['id']}/simulate",
        json={"date": "2026-10-20", "amount": "3000", "mode": "reduce_payment"},
    ).json()

    assert (term["fee"], term["fee_percent"], term["legal_cap"]) == ("30.00", "1.0000", "1.0000")
    assert term["payments_saved"] > 0
    assert term["payment_after"] == term["payment_before"]
    assert payment["payments_saved"] == 0
    assert Decimal(payment["payment_after"]) < Decimal(payment["payment_before"])
    assert Decimal(term["interest_saved"]) > Decimal(payment["interest_saved"]) > 0
    # Nothing was stored.
    assert len(schedule(ana, loan)) == 48


def test_the_fee_never_exceeds_the_legal_cap(ana: TestClient) -> None:
    mortgage = new_loan(
        ana,
        kind="mortgage",
        principal="100000",
        term_months=240,
        rate_type="variable",
        fixed_rate="2",
        fixed_months=12,
        index="euribor_12m",
        spread="1",
        early_repayment_fee="1",
    )

    result = ana.post(
        f"/api/loans/{mortgage['id']}/simulate",
        json={"date": "2026-11-01", "amount": "10000"},
    ).json()

    assert (result["fee_percent"], result["fee"]) == ("0.2500", "25.00")  # Ley 5/2019


def test_register_and_remove_an_early_repayment(ana: TestClient) -> None:
    loan = new_loan(ana, early_repayment_fee="0.5")

    after = ana.post(
        f"/api/loans/{loan['id']}/prepayments",
        json={"date": "2026-10-10", "amount": "2000", "mode": "reduce_term"},
    ).json()

    assert Decimal(after["outstanding"]) == Decimal(loan["outstanding"]) - 2000
    assert after["payments_left"] < loan["payments_left"]
    prepayments = ana.get(f"/api/loans/{loan['id']}/prepayments").json()
    assert [(p["amount"], p["fee"]) for p in prepayments] == [("2000.00", "10.00")]

    ana.delete(f"/api/loans/{loan['id']}/prepayments/{prepayments[0]['id']}").raise_for_status()
    assert ana.get(f"/api/loans/{loan['id']}").json()["outstanding"] == loan["outstanding"]


def test_cannot_repay_more_than_is_owed(ana: TestClient) -> None:
    loan = new_loan(ana)

    response = ana.post(
        f"/api/loans/{loan['id']}/prepayments", json={"date": "2026-10-10", "amount": "50000"}
    )

    assert response.status_code == 422


def test_money_lent_to_someone(ana: TestClient) -> None:
    loan = new_loan(
        ana,
        name="A mi hermana",
        kind="p2p_lent",
        lender="Lucía",
        principal="600",
        fixed_rate="0",
        term_months=6,
    )

    assert loan["direction"] == "owed"
    assert {r["payment"] for r in schedule(ana, loan)} == {"100.00"}


def test_edit_and_archive(ana: TestClient) -> None:
    loan = new_loan(ana)

    edited = ana.patch(f"/api/loans/{loan['id']}", json={"fixed_rate": "5"}).json()
    assert Decimal(edited["interest_left"]) < Decimal(loan["interest_left"])

    ana.patch(f"/api/loans/{loan['id']}", json={"archived": True}).raise_for_status()
    assert ana.get("/api/loans").json() == []
    assert len(ana.get("/api/loans", params={"include_archived": True}).json()) == 1


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"rate_type": "variable"}, "índice y el diferencial"),
        ({"first_payment": "2025-12-01"}, "anterior a la firma"),
        ({"grace_months": 48}, "carencia"),
        ({"principal": "0"}, "mayor que cero"),
    ],
)
def test_validation(ana: TestClient, fields: dict[str, Any], message: str) -> None:
    body = {
        "name": "X",
        "principal": "1000",
        "signed_on": "2026-01-10",
        "first_payment": "2026-02-05",
        "term_months": 48,
        "fixed_rate": "5",
        **fields,
    }
    response = ana.post("/api/loans", json=body)

    assert response.status_code == 422
    assert message in response.json()["error"]["message"]


def test_euribor_values_are_shared_and_updated(ana: TestClient, bea: TestClient) -> None:
    ana.put("/api/reference-rates", json={"month": "2026-09-14", "value": "2.17"})
    bea.put("/api/reference-rates", json={"month": "2026-09-01", "value": "2.18"})

    rows = ana.get("/api/reference-rates").json()

    assert [(r["month"], r["value"]) for r in rows] == [("2026-09-01", "2.1800")]
    assert ana.delete(f"/api/reference-rates/{rows[0]['id']}").status_code == 403
    assert bea.delete(f"/api/reference-rates/{rows[0]['id']}").status_code == 204


def test_loans_are_private(ana: TestClient, bea: TestClient) -> None:
    loan = new_loan(ana)

    assert bea.get("/api/loans").json() == []
    assert bea.get(f"/api/loans/{loan['id']}/schedule").status_code == 404

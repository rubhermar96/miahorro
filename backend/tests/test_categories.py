"""Categories (RF-MOV-02)."""

from typing import Any

from fastapi.testclient import TestClient

from app.defaults import DEFAULT_CATEGORIES
from tests.test_accounts import new_account
from tests.test_transactions import add, category_id


def by_name(client: TestClient, **params: Any) -> dict[str, Any]:
    return {c["name"]: c for c in client.get("/api/categories", params=params).json()}


def test_every_user_starts_with_the_spanish_defaults_once(ana: TestClient) -> None:
    first = ana.get("/api/categories").json()
    second = ana.get("/api/categories").json()

    expected = sum(1 + len(children) for _, _, _, children in DEFAULT_CATEGORIES)
    assert len(first) == len(second) == expected
    names = {c["name"] for c in first}
    assert {"Vivienda", "Supermercado", "Nómina", "Comisiones bancarias"} <= names


def test_main_categories_come_before_their_subcategories(ana: TestClient) -> None:
    categories = ana.get("/api/categories").json()
    housing = next(i for i, c in enumerate(categories) if c["name"] == "Vivienda")

    assert categories[housing + 1]["parent_id"] == categories[housing]["id"]
    assert all(c["kind"] == "expense" for c in categories[:housing])


def test_create_a_subcategory(ana: TestClient) -> None:
    leisure = category_id(ana, "Ocio")

    created = ana.post(
        "/api/categories",
        json={"name": " Conciertos ", "kind": "expense", "parent_id": leisure, "icon": "🎸"},
    )

    assert created.status_code == 201
    assert (created.json()["name"], created.json()["parent_id"]) == ("Conciertos", leisure)


def test_category_rules(ana: TestClient) -> None:
    groceries = category_id(ana, "Supermercado")
    leisure = category_id(ana, "Ocio")

    duplicate = ana.post("/api/categories", json={"name": "vivienda", "kind": "expense"})
    third_level = ana.post(
        "/api/categories", json={"name": "Bio", "kind": "expense", "parent_id": groceries}
    )
    mixed = ana.post(
        "/api/categories", json={"name": "Premios", "kind": "income", "parent_id": leisure}
    )

    assert duplicate.status_code == 409
    assert third_level.status_code == 422
    assert mixed.status_code == 422


def test_rename_and_archive(ana: TestClient) -> None:
    pets = category_id(ana, "Mascotas")

    ana.patch(f"/api/categories/{pets}", json={"name": "Perro"})
    ana.patch(f"/api/categories/{pets}", json={"archived": True})

    assert "Perro" not in by_name(ana)
    assert by_name(ana, include_archived=True)["Perro"]["archived"] is True


def test_used_categories_are_archived_not_deleted(ana: TestClient) -> None:
    account = new_account(ana)["id"]
    groceries = category_id(ana, "Supermercado")
    add(ana, account, "expense", "20", category_id=groceries)

    assert ana.delete(f"/api/categories/{groceries}").status_code == 409
    assert ana.delete(f"/api/categories/{category_id(ana, 'Alimentación')}").status_code == 409
    assert ana.delete(f"/api/categories/{category_id(ana, 'Óptica')}").status_code == 204


def test_recent_use_ranks_the_quick_add_screen(ana: TestClient) -> None:
    account = new_account(ana)["id"]
    coffee = category_id(ana, "Cafeterías y bares")
    for day in ("2026-10-01", "2026-10-02", "2026-06-01"):  # the last one is too old
        add(ana, account, "expense", "1.5", category_id=coffee, date=day)

    assert by_name(ana)["Cafeterías y bares"]["recent_uses"] == 2


def test_categories_are_per_user(ana: TestClient, bea: TestClient) -> None:
    ana.post("/api/categories", json={"name": "Secreta", "kind": "expense"})
    secret = category_id(ana, "Secreta")

    assert "Secreta" not in by_name(bea)
    assert bea.patch(f"/api/categories/{secret}", json={"name": "x"}).status_code == 404
    assert bea.delete(f"/api/categories/{secret}").status_code == 404

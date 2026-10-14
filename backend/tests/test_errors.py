import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def app_with_test_routes(app_without_db: FastAPI) -> FastAPI:
    @app_without_db.get("/api/_test/items/{item_id}")
    def read_item(item_id: int) -> dict[str, int]:
        return {"item_id": item_id}

    @app_without_db.get("/api/_test/boom")
    def boom() -> None:
        raise RuntimeError("secret internal detail")

    return app_without_db


@pytest.fixture
def test_client(app_with_test_routes: FastAPI) -> TestClient:
    return TestClient(app_with_test_routes, raise_server_exceptions=False)


def test_unknown_route_returns_uniform_spanish_error(test_client: TestClient) -> None:
    response = test_client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "No se ha encontrado el recurso.",
            "details": None,
        }
    }


def test_validation_error_does_not_echo_submitted_values(test_client: TestClient) -> None:
    response = test_client.get("/api/_test/items/1234,56")

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["details"][0]["loc"] == ["path", "item_id"]
    assert "1234,56" not in response.text


def test_unhandled_error_hides_internal_details(
    test_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR):
        response = test_client.get("/api/_test/boom")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "secret internal detail" not in response.text
    assert "Unhandled error on GET /api/_test/boom" in caplog.text


def test_access_log_omits_query_string(
    test_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="miahorro.access"):
        test_client.get("/api/_test/items/7?importe=1234.56")

    assert "GET /api/_test/items/7 200" in caplog.text
    assert "importe" not in caplog.text
    assert "1234.56" not in caplog.text

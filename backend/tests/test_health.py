from fastapi.testclient import TestClient

from app import __version__


def test_health_ok_when_database_responds(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__, "database": "ok"}


def test_health_degraded_when_database_is_down(client_without_db: TestClient) -> None:
    response = client_without_db.get("/api/health")

    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "version": __version__,
        "database": "unavailable",
    }

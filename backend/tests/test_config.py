import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.main import create_app
from tests.conftest import UNREACHABLE_DATABASE_URL, make_settings


def test_refuses_to_start_without_required_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("MIAHORRO_DATABASE_URL", "MIAHORRO_SECRET_KEY"):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ValidationError) as excinfo:
        Settings(_env_file=None)

    missing = {error["loc"][0] for error in excinfo.value.errors()}
    assert missing == {"database_url", "secret_key"}


def test_rejects_short_secret_key() -> None:
    with pytest.raises(ValidationError):
        make_settings(secret_key="too-short")


def test_reads_configuration_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MIAHORRO_DATABASE_URL", UNREACHABLE_DATABASE_URL)
    monkeypatch.setenv("MIAHORRO_SECRET_KEY", "x" * 40)
    monkeypatch.setenv("MIAHORRO_ENVIRONMENT", "production")

    settings = Settings(_env_file=None)

    assert settings.is_production
    assert settings.secret_key.get_secret_value() == "x" * 40


def test_production_hides_api_docs() -> None:
    app = create_app(make_settings(environment="production", database_url=UNREACHABLE_DATABASE_URL))
    with TestClient(app) as client:
        assert client.get("/api/docs").status_code == 404
        assert client.get("/api/openapi.json").status_code == 404


def test_development_exposes_api_docs(client_without_db: TestClient) -> None:
    assert client_without_db.get("/api/openapi.json").status_code == 200

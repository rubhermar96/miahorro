import os
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from app.config import Settings
from app.main import create_app

TEST_DATABASE_URL = os.environ.get(
    "MIAHORRO_TEST_DATABASE_URL",
    "postgresql+psycopg://miahorro:miahorro@localhost:5432/miahorro_test",
)
# Nothing listens on port 1; the short timeout keeps tests fast.
UNREACHABLE_DATABASE_URL = "postgresql+psycopg://nobody:nothing@127.0.0.1:1/none?connect_timeout=1"


def make_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "environment": "test",
        "database_url": TEST_DATABASE_URL,
        "secret_key": "test-secret-key-not-for-production-0000000",
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.fixture(scope="session")
def database_url() -> str:
    """URL of the test database. Skips locally if it is not running; fails in CI."""
    engine = create_engine(TEST_DATABASE_URL)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError:
        if os.environ.get("CI"):
            raise
        pytest.skip("No test database: start it with `docker compose up -d db`")
    finally:
        engine.dispose()
    return TEST_DATABASE_URL


def _client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
    app.state.engine.dispose()


@pytest.fixture
def client(database_url: str) -> Iterator[TestClient]:
    """Client backed by the real test database."""
    yield from _client(create_app(make_settings(database_url=database_url)))


@pytest.fixture
def app_without_db() -> FastAPI:
    """App whose database is unreachable; for tests that must not touch PostgreSQL."""
    return create_app(make_settings(database_url=UNREACHABLE_DATABASE_URL))


@pytest.fixture
def client_without_db(app_without_db: FastAPI) -> Iterator[TestClient]:
    yield from _client(app_without_db)

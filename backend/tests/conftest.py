import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app import clock
from app.auth.csrf import CSRF_HEADER
from app.config import Settings
from app.db import Base
from app.main import create_app

TEST_DATABASE_URL = os.environ.get(
    "MIAHORRO_TEST_DATABASE_URL",
    "postgresql+psycopg://miahorro:miahorro@127.0.0.1:15432/miahorro_test",
)
# Nothing listens on port 1; the short timeout keeps tests fast.
UNREACHABLE_DATABASE_URL = "postgresql+psycopg://nobody:nothing@127.0.0.1:1/none?connect_timeout=1"
ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def make_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "environment": "test",
        "database_url": TEST_DATABASE_URL,
        "secret_key": "test-secret-key-not-for-production-0000000",
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)


def alembic_config(database_url: str) -> Config:
    config = Config(ALEMBIC_INI)
    config.attributes["database_url"] = database_url
    config.attributes["configure_logger"] = False
    return config


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


@pytest.fixture(scope="session")
def migrated_database(database_url: str) -> str:
    command.upgrade(alembic_config(database_url), "head")
    return database_url


def _truncate_all(engine: Engine) -> None:
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    if tables:
        with engine.begin() as connection:
            connection.execute(text(f"TRUNCATE {tables} CASCADE"))


@pytest.fixture
def app(migrated_database: str) -> Iterator[FastAPI]:
    """App on the real test database, emptied before each test."""
    application = create_app(make_settings(database_url=migrated_database))
    _truncate_all(application.state.engine)
    yield application
    application.state.engine.dispose()


def new_client(app: FastAPI, base_url: str = "http://testserver") -> TestClient:
    """A separate browser: its own cookies. Sends the anti-CSRF header like the real app."""
    return TestClient(
        app, base_url=base_url, raise_server_exceptions=False, headers={CSRF_HEADER: "1"}
    )


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with new_client(app) as test_client:
        yield test_client


@pytest.fixture
def db(app: FastAPI) -> Iterator[Session]:
    with app.state.session_factory() as session:
        yield session


@pytest.fixture
def app_without_db() -> FastAPI:
    """App whose database is unreachable; for tests that must not touch PostgreSQL."""
    return create_app(make_settings(database_url=UNREACHABLE_DATABASE_URL))


@pytest.fixture
def client_without_db(app_without_db: FastAPI) -> Iterator[TestClient]:
    with TestClient(app_without_db, raise_server_exceptions=False) as test_client:
        yield test_client
    app_without_db.state.engine.dispose()


class FakeClock:
    def __init__(self, start: datetime) -> None:
        self.current = start

    def now(self) -> datetime:
        return self.current

    def advance(self, **delta: float) -> None:
        self.current += timedelta(**delta)


@pytest.fixture
def fake_clock(monkeypatch: pytest.MonkeyPatch) -> FakeClock:
    fake = FakeClock(datetime(2026, 10, 15, 10, 0, tzinfo=UTC))
    monkeypatch.setattr(clock, "now", fake.now)
    return fake


def _signed_in(app: FastAPI, email: str) -> Iterator[TestClient]:
    from tests.helpers import create_user, sign_in

    _, secret = create_user(app, email, with_totp=True)
    assert secret
    with new_client(app) as client:
        sign_in(client, email, secret)
        yield client


@pytest.fixture
def ana(app: FastAPI, fake_clock: FakeClock) -> Iterator[TestClient]:
    """Ana, signed in. Today is 15/10/2026 (fake clock)."""
    yield from _signed_in(app, "ana@example.com")


@pytest.fixture
def bea(app: FastAPI, fake_clock: FakeClock) -> Iterator[TestClient]:
    """Another user, to check that nobody sees anyone else's data."""
    yield from _signed_in(app, "bea@example.com")

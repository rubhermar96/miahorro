from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from sqlalchemy import select
from typer.testing import CliRunner

from app.cli import cli
from app.config import get_settings
from app.models.auth import AuthSession
from app.models.user import User
from app.reference_data import SEED
from tests.conftest import FakeClock
from tests.helpers import create_user, sign_in

runner = CliRunner()


@pytest.fixture(autouse=True)
def cli_environment(
    app: FastAPI, migrated_database: str, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    monkeypatch.setenv("MIAHORRO_DATABASE_URL", migrated_database)
    monkeypatch.setenv("MIAHORRO_SECRET_KEY", app.state.settings.secret_key.get_secret_value())
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _users(app: FastAPI) -> list[User]:
    with app.state.session_factory() as db:
        return list(db.scalars(select(User)))


def test_create_admin_user(app: FastAPI) -> None:
    result = runner.invoke(
        cli,
        [
            "create-user",
            "--email",
            "Ana@Example.com",
            "--name",
            "Ana",
            "--admin",
            "--password-stdin",
        ],
        input="una-contraseña-muy-larga\n",
    )

    assert result.exit_code == 0, result.output
    [user] = _users(app)
    assert (user.email, user.display_name, user.is_admin) == ("ana@example.com", "Ana", True)
    assert user.password_hash is not None
    assert user.password_hash.startswith("$argon2")


def test_refuses_short_passwords_and_duplicates(app: FastAPI) -> None:
    short = runner.invoke(
        cli,
        ["create-user", "--email", "a@b.com", "--name", "A", "--password-stdin"],
        input="corta\n",
    )
    create_user(app, "a@b.com")
    duplicate = runner.invoke(
        cli,
        ["create-user", "--email", "a@b.com", "--name", "A", "--password-stdin"],
        input="una-contraseña-muy-larga\n",
    )

    assert short.exit_code == 1
    assert "12 caracteres" in short.output
    assert duplicate.exit_code == 1
    assert len(_users(app)) == 1


def test_reset_mfa_removes_second_factor_and_sessions(
    app: FastAPI, client: object, fake_clock: FakeClock
) -> None:
    from fastapi.testclient import TestClient

    assert isinstance(client, TestClient)
    _, secret = create_user(app, with_totp=True)
    assert secret
    sign_in(client, "ana@example.com", secret)

    result = runner.invoke(cli, ["reset-mfa", "--email", "ana@example.com"])

    assert result.exit_code == 0, result.output
    [user] = _users(app)
    assert user.totp_enabled_at is None
    with app.state.session_factory() as db:
        assert db.scalars(select(AuthSession)).all() == []
    assert client.get("/api/me").status_code == 401


def test_list_users(app: FastAPI) -> None:
    create_user(app, "ana@example.com", admin=True, with_totp=True)

    result = runner.invoke(cli, ["list-users"])

    assert "ana@example.com" in result.output
    assert "admin, 2FA" in result.output


def test_sync_reference_values_adds_only_what_is_missing() -> None:
    first = runner.invoke(cli, ["sync-reference-values"])
    again = runner.invoke(cli, ["sync-reference-values"])

    assert first.exit_code == 0
    assert f"añadidos: {len(SEED)}" in first.output
    assert "añadidos: 0" in again.output


def test_summary_for_comparing_databases(app: FastAPI) -> None:
    create_user(app, "ana@example.com", with_totp=True)

    result = runner.invoke(cli, ["summary"])

    assert result.exit_code == 0, result.output
    assert "  users: 1" in result.output
    assert "ana@example.com: 0 movimientos · cuentas 0.00" in result.output

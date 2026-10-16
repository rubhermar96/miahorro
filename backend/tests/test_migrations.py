from pathlib import Path

from alembic import command
from alembic.config import Config

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def _alembic_config(database_url: str) -> Config:
    config = Config(ALEMBIC_INI)
    config.attributes["database_url"] = database_url
    config.attributes["configure_logger"] = False
    return config


def test_migrations_upgrade_and_downgrade(database_url: str) -> None:
    config = _alembic_config(database_url)

    command.upgrade(config, "head")
    command.downgrade(config, "base")
    command.upgrade(config, "head")


def test_models_and_migrations_are_in_sync(database_url: str) -> None:
    config = _alembic_config(database_url)
    command.upgrade(config, "head")

    # Fails if a model changed without a matching migration.
    command.check(config)

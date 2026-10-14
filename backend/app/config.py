from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from MIAHORRO_* environment variables.

    There are deliberately no defaults for the database URL or the secret key:
    the API must refuse to start rather than run with an insecure setup.
    """

    model_config = SettingsConfigDict(env_prefix="MIAHORRO_", env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    database_url: PostgresDsn
    secret_key: SecretStr = Field(min_length=32)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # values come from the environment

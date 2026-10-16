from functools import lru_cache
from typing import Literal, Self

from pydantic import AnyHttpUrl, Field, PostgresDsn, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_PORTS = {"http": 80, "https": 443}
# Vite's dev server, which proxies /api to the API (see frontend/vite.config.ts).
_VITE_DEV_ORIGIN = "http://localhost:5173"


class Settings(BaseSettings):
    """Runtime configuration, read from MIAHORRO_* environment variables.

    There are deliberately no defaults for the database URL or the secret key:
    the API must refuse to start rather than run with an insecure setup.

    The secret key also encrypts TOTP secrets and keys recovery codes, so changing it means
    every user has to set up their authenticator app again.
    """

    model_config = SettingsConfigDict(env_prefix="MIAHORRO_", env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    database_url: PostgresDsn
    secret_key: SecretStr = Field(min_length=32)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Address users open the app at; passkeys are bound to its host name.
    public_url: AnyHttpUrl = AnyHttpUrl("http://localhost:8080")

    # Open sign-up (D22). The first account becomes the administrator; the cap protects the
    # shared VPS, and registration can be closed at any time without touching anything else.
    registration_enabled: bool = True
    max_users: int = Field(default=20, ge=1)

    session_idle_days: int = Field(default=30, ge=1)
    session_max_days: int = Field(default=90, ge=1)
    login_max_attempts: int = Field(default=5, ge=1)
    login_lockout_minutes: int = Field(default=15, ge=1)

    @model_validator(mode="after")
    def _production_requires_https(self) -> Self:
        if self.is_production and self.public_url.scheme != "https":
            raise ValueError("MIAHORRO_PUBLIC_URL must use https in production")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def public_origin(self) -> str:
        url = self.public_url
        port = "" if url.port == _DEFAULT_PORTS.get(url.scheme) else f":{url.port}"
        return f"{url.scheme}://{url.host}{port}"

    @property
    def webauthn_rp_id(self) -> str:
        return str(self.public_url.host)

    @property
    def webauthn_origins(self) -> list[str]:
        origins = [self.public_origin]
        if not self.is_production and _VITE_DEV_ORIGIN not in origins:
            origins.append(_VITE_DEV_ORIGIN)
        return origins

    @property
    def session_cookie_name(self) -> str:
        # The __Host- prefix makes browsers insist on Secure, Path=/ and no Domain. Safari
        # rejects Secure cookies over plain http, so development uses a plain name.
        return "__Host-miahorro_session" if self.is_production else "miahorro_session"

    @property
    def secure_cookies(self) -> bool:
        return self.is_production


@lru_cache
def get_settings() -> Settings:
    return Settings()  # values come from the environment

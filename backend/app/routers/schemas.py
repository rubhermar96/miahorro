"""Request and response bodies shared by the account endpoints."""

import re
import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.auth import factors
from app.models.auth import PasskeyCredential
from app.models.user import User

SessionLevel = Literal["full", "mfa_pending", "mfa_setup"]
Theme = Literal["system", "light", "dark"]
Language = Literal["es"]
Currency = Literal["EUR", "USD", "GBP", "CHF"]  # same list as app.models.user.CURRENCIES


class Preferences(BaseModel):
    currency: Currency
    month_start_day: int = Field(ge=1, le=28)
    theme: Theme
    language: Language


class PreferencesUpdate(BaseModel):
    currency: Currency | None = None
    month_start_day: int | None = Field(default=None, ge=1, le=28)
    theme: Theme | None = None
    language: Language | None = None


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    is_admin: bool
    has_totp: bool
    has_passkey: bool
    recovery_codes_left: int
    preferences: Preferences

    @classmethod
    def from_user(cls, db: Session, user: User) -> UserOut:
        return cls(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            is_admin=user.is_admin,
            has_totp=user.has_totp,
            has_passkey=factors.passkey_count(db, user) > 0,
            recovery_codes_left=factors.recovery_codes_left(db, user),
            preferences=Preferences(
                currency=user.currency,  # constrained in the database
                month_start_day=user.month_start_day,
                theme=user.theme,
                language=user.language,
            ),
        )


class SessionOut(BaseModel):
    level: SessionLevel
    user: UserOut


class LoginRequest(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=1024)

    @field_validator("email")
    @classmethod
    def _normalise_email(cls, value: str) -> str:
        return value.strip().lower()


_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegisterRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)
    email: str = Field(max_length=254)
    password: str = Field(max_length=1024)

    @field_validator("display_name")
    @classmethod
    def _clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Escribe tu nombre.")
        return value

    @field_validator("email")
    @classmethod
    def _check_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not _EMAIL_PATTERN.match(value):
            raise ValueError("El email no es válido.")
        return value


class RegistrationStatus(BaseModel):
    open: bool


class LoginResult(BaseModel):
    status: Literal["authenticated", "mfa_required", "mfa_setup_required"]


class MfaRequest(BaseModel):
    code: str | None = Field(default=None, max_length=16)
    recovery_code: str | None = Field(default=None, max_length=32)


class TotpSetup(BaseModel):
    secret: str
    otpauth_uri: str
    qr_code: str = Field(description="SVG QR code as a data: URI")


class CodeRequest(BaseModel):
    code: str = Field(max_length=16)


class RecoveryCodes(BaseModel):
    codes: list[str]


class PasskeyOptions(BaseModel):
    challenge_id: uuid.UUID
    options: dict[str, Any]


class PasskeyRegistration(BaseModel):
    challenge_id: uuid.UUID
    credential: dict[str, Any]
    name: str = Field(min_length=1, max_length=60)


class PasskeyAssertion(BaseModel):
    challenge_id: uuid.UUID
    credential: dict[str, Any]


class PasskeyOut(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    last_used_at: datetime | None

    @classmethod
    def from_model(cls, passkey: PasskeyCredential) -> PasskeyOut:
        return cls(
            id=passkey.id,
            name=passkey.name,
            created_at=passkey.created_at,
            last_used_at=passkey.last_used_at,
        )

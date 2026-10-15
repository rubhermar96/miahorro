"""WebAuthn (passkeys: Face ID, Touch ID, security keys) on top of the `webauthn` library."""

import json
import secrets
import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy.orm import Session
from webauthn import (
    base64url_to_bytes,
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app import clock
from app.config import Settings
from app.models.auth import AuthChallenge, PasskeyCredential
from app.models.user import User

RP_NAME = "MiAhorro"
PURPOSE_REGISTER = "passkey_register"
PURPOSE_LOGIN = "passkey_login"
_CHALLENGE_LIFETIME = timedelta(minutes=5)


class PasskeyError(Exception):
    """The browser's response could not be verified."""


def _store_challenge(db: Session, purpose: str, user: User | None) -> AuthChallenge:
    challenge = AuthChallenge(
        id=uuid.uuid4(),
        user_id=user.id if user else None,
        purpose=purpose,
        challenge=secrets.token_bytes(32),
        expires_at=clock.now() + _CHALLENGE_LIFETIME,
    )
    db.add(challenge)
    return challenge


def take_challenge(
    db: Session, challenge_id: uuid.UUID, purpose: str, user: User | None
) -> AuthChallenge:
    """Fetch and consume a challenge: each one can be answered only once."""
    challenge = db.get(AuthChallenge, challenge_id)
    if challenge is None:
        raise PasskeyError("unknown challenge")
    db.delete(challenge)
    if not challenge.is_valid_for(purpose, user.id if user else None, clock.now()):
        raise PasskeyError("expired or mismatched challenge")
    return challenge


def registration_options(
    db: Session, user: User, existing: list[PasskeyCredential], settings: Settings
) -> tuple[uuid.UUID, dict[str, Any]]:
    challenge = _store_challenge(db, PURPOSE_REGISTER, user)
    options = generate_registration_options(
        rp_id=settings.webauthn_rp_id,
        rp_name=RP_NAME,
        user_id=user.id.bytes,
        user_name=user.email,
        user_display_name=user.display_name,
        challenge=challenge.challenge,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        exclude_credentials=[
            PublicKeyCredentialDescriptor(id=passkey.credential_id) for passkey in existing
        ],
    )
    return challenge.id, json.loads(options_to_json(options))


def verify_registration(
    challenge: AuthChallenge, credential: dict[str, Any], settings: Settings
) -> tuple[bytes, bytes, int, list[str]]:
    """Return (credential_id, public_key, sign_count, transports)."""
    try:
        verified = verify_registration_response(
            credential=credential,
            expected_challenge=challenge.challenge,
            expected_rp_id=settings.webauthn_rp_id,
            expected_origin=settings.webauthn_origins,
            require_user_verification=True,
        )
    except Exception as exc:  # the library raises several unrelated types
        raise PasskeyError(str(exc)) from exc
    transports = credential.get("response", {}).get("transports") or []
    return (
        verified.credential_id,
        verified.credential_public_key,
        verified.sign_count,
        [str(t) for t in transports],
    )


def authentication_options(db: Session, settings: Settings) -> tuple[uuid.UUID, dict[str, Any]]:
    # No allow-list: the phone offers the passkeys it holds for this site (discoverable).
    challenge = _store_challenge(db, PURPOSE_LOGIN, None)
    options = generate_authentication_options(
        rp_id=settings.webauthn_rp_id,
        challenge=challenge.challenge,
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    return challenge.id, json.loads(options_to_json(options))


def credential_id_of(credential: dict[str, Any]) -> bytes:
    try:
        return base64url_to_bytes(str(credential["rawId"]))
    except (KeyError, ValueError) as exc:
        raise PasskeyError("missing credential id") from exc


def verify_authentication(
    challenge: AuthChallenge,
    credential: dict[str, Any],
    passkey: PasskeyCredential,
    settings: Settings,
) -> int:
    """Return the new signature counter."""
    try:
        verified = verify_authentication_response(
            credential=credential,
            expected_challenge=challenge.challenge,
            expected_rp_id=settings.webauthn_rp_id,
            expected_origin=settings.webauthn_origins,
            credential_public_key=passkey.public_key,
            credential_current_sign_count=passkey.sign_count,
            require_user_verification=True,
        )
    except Exception as exc:
        raise PasskeyError(str(exc)) from exc
    return verified.new_sign_count

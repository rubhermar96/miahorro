"""Registration, sign-in and account security (RF-USR-01, RF-PLT-03).

Rules (D23):
- A passkey (Face ID) is the main way in: enough on its own, since it proves possession and
  identity.
- A password always needs a second factor: a passkey or the authenticator app (TOTP). After
  the password the session is "mfa_pending" (confirm with either), or "mfa_setup" when the user
  has neither yet and must set one up now.
- Wrong passwords and codes count towards a temporary lockout.
- The session token changes whenever the session gains privileges.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from sqlalchemy import func, select

from app import clock
from app.auth import factors, lockout, passkeys, sessions
from app.auth.deps import (
    AppSettings,
    CurrentAuthSession,
    CurrentUser,
    DbSession,
    EnrollingAuthSession,
    FullAuthSession,
)
from app.config import Settings
from app.models.auth import (
    LEVEL_FULL,
    LEVEL_MFA_PENDING,
    LEVEL_MFA_SETUP,
    AuthSession,
    PasskeyCredential,
    RecoveryCode,
)
from app.models.user import User
from app.ownership import get_owned_or_404, owned
from app.routers.schemas import (
    CodeRequest,
    LoginRequest,
    LoginResult,
    MfaRequest,
    PasskeyAssertion,
    PasskeyOptions,
    PasskeyOut,
    PasskeyRegistration,
    RecoveryCodes,
    RegisterRequest,
    RegistrationStatus,
    SessionOut,
    TotpSetup,
    UserOut,
)
from app.security import encryption, passwords, recovery, totp

router = APIRouter(prefix="/api/auth", tags=["auth"])

UserAgent = Annotated[str | None, Header()]

_BAD_CREDENTIALS = "Email o contraseña incorrectos."
_BAD_CODE = "El código no es correcto."
_BAD_PASSKEY = "No se ha podido verificar la passkey."


def _start_session(
    db: DbSession,
    response: Response,
    user: User,
    level: str,
    settings: Settings,
    user_agent: str | None,
    replaces: AuthSession | None = None,
) -> None:
    if replaces is not None:
        sessions.revoke(db, replaces)
    token = sessions.create(db, user, level, settings, user_agent)
    db.commit()
    sessions.set_cookie(response, token, settings)


def _issue_recovery_codes(db: DbSession, user: User, settings: Settings) -> list[str]:
    secret_key = settings.secret_key.get_secret_value()
    for existing in db.scalars(owned(RecoveryCode, user)):
        db.delete(existing)
    codes = recovery.new_codes()
    for code in codes:
        db.add(RecoveryCode(user_id=user.id, code_hash=recovery.hash_code(secret_key, code)))
    return codes


# --- Registration (D22) -----------------------------------------------------------------------


def _registration_open(db: DbSession, settings: Settings) -> bool:
    if not settings.registration_enabled:
        return False
    users = db.scalar(select(func.count()).select_from(User)) or 0
    return users < settings.max_users


@router.get("/registration")
def registration_status(db: DbSession, settings: AppSettings) -> RegistrationStatus:
    return RegistrationStatus(open=_registration_open(db, settings))


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterRequest,
    response: Response,
    db: DbSession,
    settings: AppSettings,
    user_agent: UserAgent = None,
) -> LoginResult:
    """Create an account. The second factor is set up straight away, as on a first sign-in."""
    if not _registration_open(db, settings):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "El registro de cuentas está cerrado.")
    try:
        passwords.validate_new_password(body.password)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    if db.scalar(select(User.id).where(User.email == body.email)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe una cuenta con ese email.")

    is_first_user = db.scalar(select(User.id).limit(1)) is None
    user = User(
        email=body.email,
        display_name=body.display_name,
        password_hash=passwords.hash_password(body.password),
        is_admin=is_first_user,
    )
    db.add(user)
    db.flush()
    _start_session(db, response, user, LEVEL_MFA_SETUP, settings, user_agent)
    return LoginResult(status="mfa_setup_required")


# --- Password and second factor -------------------------------------------------------------


@router.post("/login")
def login(
    body: LoginRequest,
    response: Response,
    db: DbSession,
    settings: AppSettings,
    user_agent: UserAgent = None,
) -> LoginResult:
    user = db.scalar(select(User).where(User.email == body.email))
    if user is not None:
        lockout.ensure_not_locked(user)

    valid, new_hash = passwords.verify_password(body.password, user.password_hash if user else None)
    if user is None or not user.is_active or not valid:
        if user is not None:
            lockout.register_failure(user, settings)
            db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, _BAD_CREDENTIALS)

    if new_hash:
        user.password_hash = new_hash
    lockout.register_success(user)
    # Second step: Face ID (passkey) or the authenticator app; without either, set one up now.
    if factors.has_second_factor(db, user):
        _start_session(db, response, user, LEVEL_MFA_PENDING, settings, user_agent)
        return LoginResult(status="mfa_required")
    _start_session(db, response, user, LEVEL_MFA_SETUP, settings, user_agent)
    return LoginResult(status="mfa_setup_required")


@router.post("/mfa")
def verify_second_factor(
    body: MfaRequest,
    response: Response,
    auth: CurrentAuthSession,
    db: DbSession,
    settings: AppSettings,
    user_agent: UserAgent = None,
) -> LoginResult:
    if auth.level != LEVEL_MFA_PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, "No hay ningún código pendiente.")
    user = auth.user
    lockout.ensure_not_locked(user)

    if body.code:
        ok = _accept_totp(user, body.code, settings)
    elif body.recovery_code:
        ok = _accept_recovery_code(db, user, body.recovery_code, settings)
    else:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Introduce un código.")

    if not ok:
        lockout.register_failure(user, settings)
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, _BAD_CODE)

    lockout.register_success(user)
    _start_session(db, response, user, LEVEL_FULL, settings, user_agent, replaces=auth)
    return LoginResult(status="authenticated")


def _accept_totp(user: User, code: str, settings: Settings) -> bool:
    if user.totp_secret_encrypted is None:
        return False
    secret = encryption.decrypt(settings.secret_key.get_secret_value(), user.totp_secret_encrypted)
    step = totp.verify(secret, code, clock.now(), user.totp_last_used_step)
    if step is None:
        return False
    user.totp_last_used_step = step
    return True


def _accept_recovery_code(db: DbSession, user: User, code: str, settings: Settings) -> bool:
    code_hash = recovery.hash_code(settings.secret_key.get_secret_value(), code)
    match = db.scalar(
        owned(RecoveryCode, user).where(
            RecoveryCode.code_hash == code_hash, RecoveryCode.used_at.is_(None)
        )
    )
    if match is None:
        return False
    match.used_at = clock.now()
    return True


@router.post("/totp/setup")
def start_totp_setup(auth: CurrentAuthSession, db: DbSession, settings: AppSettings) -> TotpSetup:
    """Generate a new authenticator secret. It only takes effect once a code confirms it."""
    user = auth.user
    if auth.level == LEVEL_MFA_PENDING or user.has_totp:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "La verificación en dos pasos ya está activa."
        )
    secret = totp.new_secret()
    user.totp_secret_encrypted = encryption.encrypt(settings.secret_key.get_secret_value(), secret)
    db.commit()
    uri = totp.provisioning_uri(secret, user.email)
    return TotpSetup(secret=secret, otpauth_uri=uri, qr_code=totp.qr_data_uri(uri))


@router.post("/totp/confirm")
def confirm_totp_setup(
    body: CodeRequest,
    response: Response,
    auth: CurrentAuthSession,
    db: DbSession,
    settings: AppSettings,
    user_agent: UserAgent = None,
) -> RecoveryCodes:
    user = auth.user
    if auth.level == LEVEL_MFA_PENDING or user.has_totp or user.totp_secret_encrypted is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "No hay ninguna configuración pendiente.")
    lockout.ensure_not_locked(user)
    if not _accept_totp(user, body.code, settings):
        lockout.register_failure(user, settings)
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, _BAD_CODE)

    user.totp_enabled_at = clock.now()
    lockout.register_success(user)
    codes = _issue_recovery_codes(db, user, settings)
    if auth.level == LEVEL_MFA_SETUP:
        _start_session(db, response, user, LEVEL_FULL, settings, user_agent, replaces=auth)
    else:
        db.commit()
    return RecoveryCodes(codes=codes)


@router.post("/recovery-codes")
def regenerate_recovery_codes(
    user: CurrentUser, db: DbSession, settings: AppSettings
) -> RecoveryCodes:
    if not factors.has_second_factor(db, user):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Configura antes Face ID o una app de códigos."
        )
    codes = _issue_recovery_codes(db, user, settings)
    db.commit()
    return RecoveryCodes(codes=codes)


# --- Session ----------------------------------------------------------------------------------


@router.get("/session")
def current_session(auth: CurrentAuthSession, db: DbSession) -> SessionOut:
    return SessionOut.model_validate(
        {"level": auth.level, "user": UserOut.from_user(db, auth.user)}
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(auth: CurrentAuthSession, db: DbSession, settings: AppSettings) -> Response:
    sessions.revoke(db, auth)
    db.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    sessions.clear_cookie(response, settings)
    return response


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
def logout_everywhere(auth: FullAuthSession, db: DbSession, settings: AppSettings) -> Response:
    sessions.revoke_all(db, auth.user_id)
    db.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    sessions.clear_cookie(response, settings)
    return response


# --- Passkeys ---------------------------------------------------------------------------------


@router.get("/passkeys")
def list_passkeys(user: CurrentUser, db: DbSession) -> list[PasskeyOut]:
    rows = db.scalars(owned(PasskeyCredential, user).order_by(PasskeyCredential.created_at))
    return [PasskeyOut.from_model(row) for row in rows]


@router.post("/passkeys/register/options")
def passkey_registration_options(
    auth: EnrollingAuthSession, db: DbSession, settings: AppSettings
) -> PasskeyOptions:
    user = auth.user
    existing = list(db.scalars(owned(PasskeyCredential, user)))
    challenge_id, options = passkeys.registration_options(db, user, existing, settings)
    db.commit()
    return PasskeyOptions(challenge_id=challenge_id, options=options)


@router.post("/passkeys/register", status_code=status.HTTP_201_CREATED)
def register_passkey(
    body: PasskeyRegistration,
    response: Response,
    auth: EnrollingAuthSession,
    db: DbSession,
    settings: AppSettings,
    user_agent: UserAgent = None,
) -> PasskeyOut:
    """Add a passkey. During the first setup it is the second factor and completes sign-in."""
    user = auth.user
    try:
        challenge = passkeys.take_challenge(db, body.challenge_id, passkeys.PURPOSE_REGISTER, user)
        credential_id, public_key, sign_count, transports = passkeys.verify_registration(
            challenge, body.credential, settings
        )
    except passkeys.PasskeyError as exc:
        db.commit()  # the challenge is consumed either way
        raise HTTPException(status.HTTP_400_BAD_REQUEST, _BAD_PASSKEY) from exc

    passkey = PasskeyCredential(
        user_id=user.id,
        credential_id=credential_id,
        public_key=public_key,
        sign_count=sign_count,
        transports=transports,
        name=body.name.strip(),
        created_at=clock.now(),
    )
    db.add(passkey)
    if auth.level == LEVEL_MFA_SETUP:
        _start_session(db, response, user, LEVEL_FULL, settings, user_agent, replaces=auth)
    else:
        db.commit()
    return PasskeyOut.from_model(passkey)


@router.delete("/passkeys/{passkey_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_passkey(passkey_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Response:
    passkey = get_owned_or_404(db, PasskeyCredential, passkey_id, user)
    db.delete(passkey)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/passkeys/login/options")
def passkey_login_options(db: DbSession, settings: AppSettings) -> PasskeyOptions:
    challenge_id, options = passkeys.authentication_options(db, settings)
    db.commit()
    return PasskeyOptions(challenge_id=challenge_id, options=options)


@router.post("/passkeys/login")
def login_with_passkey(
    body: PasskeyAssertion,
    request: Request,
    response: Response,
    db: DbSession,
    settings: AppSettings,
    user_agent: UserAgent = None,
) -> LoginResult:
    """Sign in with a passkey alone, or finish a password sign-in with it (second factor)."""
    try:
        challenge = passkeys.take_challenge(db, body.challenge_id, passkeys.PURPOSE_LOGIN, None)
        credential_id = passkeys.credential_id_of(body.credential)
        passkey = db.scalar(
            select(PasskeyCredential).where(PasskeyCredential.credential_id == credential_id)
        )
        if passkey is None:
            raise passkeys.PasskeyError("unknown credential")
        new_sign_count = passkeys.verify_authentication(
            challenge, body.credential, passkey, settings
        )
    except passkeys.PasskeyError as exc:
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, _BAD_PASSKEY) from exc

    user = db.get(User, passkey.user_id)
    if user is None or not user.is_active:
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, _BAD_PASSKEY)

    passkey.sign_count = new_sign_count
    passkey.last_used_at = clock.now()
    lockout.register_success(user)
    # A half-finished password sign-in on this device is replaced by the full session.
    previous = sessions.load(db, request.cookies.get(settings.session_cookie_name), settings)
    _start_session(db, response, user, LEVEL_FULL, settings, user_agent, replaces=previous)
    return LoginResult(status="authenticated")

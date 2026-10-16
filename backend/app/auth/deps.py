from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth import sessions
from app.config import Settings
from app.db import get_session
from app.models.auth import LEVEL_FULL, LEVEL_MFA_SETUP, AuthSession
from app.models.user import User

DbSession = Annotated[Session, Depends(get_session)]


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


AppSettings = Annotated[Settings, Depends(get_settings)]


def get_auth_session(request: Request, db: DbSession, settings: AppSettings) -> AuthSession:
    """Any live session, whatever its level (used by the sign-in steps themselves)."""
    row = sessions.load(db, request.cookies.get(settings.session_cookie_name), settings)
    if row is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED)
    return row


CurrentAuthSession = Annotated[AuthSession, Depends(get_auth_session)]


def get_enrolling_session(auth: CurrentAuthSession) -> AuthSession:
    """A full session, or one that is setting up its first second factor."""
    if auth.level not in (LEVEL_FULL, LEVEL_MFA_SETUP):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Termina de iniciar sesión.")
    return auth


EnrollingAuthSession = Annotated[AuthSession, Depends(get_enrolling_session)]


def get_full_session(auth: CurrentAuthSession) -> AuthSession:
    if auth.level != LEVEL_FULL:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Termina de iniciar sesión.")
    return auth


FullAuthSession = Annotated[AuthSession, Depends(get_full_session)]


def get_current_user(auth: FullAuthSession) -> User:
    return auth.user


CurrentUser = Annotated[User, Depends(get_current_user)]

from fastapi import APIRouter

from app.auth.deps import CurrentUser, DbSession
from app.routers.schemas import PreferencesUpdate, UserOut

router = APIRouter(prefix="/api/me", tags=["me"])


@router.get("")
def read_me(user: CurrentUser, db: DbSession) -> UserOut:
    return UserOut.from_user(db, user)


@router.patch("/preferences")
def update_preferences(body: PreferencesUpdate, user: CurrentUser, db: DbSession) -> UserOut:
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(user, field, value)
    if "savings_rate_target" in body.model_fields_set:  # null removes it
        user.savings_rate_target = body.savings_rate_target
    db.commit()
    return UserOut.from_user(db, user)

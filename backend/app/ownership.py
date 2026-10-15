"""The only way to read rows that belong to a user (RF-PLT-01).

Every query on an OwnedMixin model goes through `owned()` or `get_owned_or_404()`, which
always filter by the current user. Another user's row is reported as missing (404), never as
forbidden, so its existence is not revealed.
"""

import uuid
from typing import Any, cast

from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.base import OwnedMixin
from app.models.user import User


def owned[T: OwnedMixin](model: type[T], user: User) -> Select[T]:
    columns = cast(Any, model)
    return select(model).where(columns.user_id == user.id)


def get_owned_or_404[T: OwnedMixin](
    db: Session, model: type[T], object_id: uuid.UUID, user: User
) -> T:
    columns = cast(Any, model)
    row = db.scalar(owned(model, user).where(columns.id == object_id))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return row

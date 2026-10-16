"""Two-level categories (RF-MOV-02). Each user starts with a Spanish default set."""

import uuid
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import exists, func, or_, select

from app import clock
from app.auth.deps import CurrentUser, DbSession
from app.defaults import ensure_default_categories
from app.models.transactions import Category, Transaction
from app.models.user import User
from app.ownership import get_owned_or_404, owned

router = APIRouter(prefix="/api/categories", tags=["categories"])

CategoryKind = Literal["expense", "income"]
# Recent use decides which categories the quick-add screen shows first.
_USAGE_WINDOW = timedelta(days=90)


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    kind: CategoryKind
    parent_id: uuid.UUID | None = None
    icon: str | None = Field(default=None, max_length=8)

    @field_validator("name")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Escribe un nombre.")
        return value


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=40)
    icon: str | None = Field(default=None, max_length=8)
    archived: bool | None = None


class CategoryOut(BaseModel):
    id: uuid.UUID
    name: str
    kind: CategoryKind
    parent_id: uuid.UUID | None
    icon: str | None
    archived: bool
    recent_uses: int = Field(description="Transactions in the last 90 days")


def _sibling_named(db: DbSession, user: User, name: str, parent_id: uuid.UUID | None) -> bool:
    return bool(
        db.scalar(
            select(
                exists().where(
                    Category.user_id == user.id,
                    func.lower(Category.name) == name.lower(),
                    Category.parent_id.is_(None)
                    if parent_id is None
                    else Category.parent_id == parent_id,
                )
            )
        )
    )


def _out(category: Category, uses: dict[uuid.UUID, int]) -> CategoryOut:
    return CategoryOut.model_validate(
        {
            "id": category.id,
            "name": category.name,
            "kind": category.kind,
            "parent_id": category.parent_id,
            "icon": category.icon,
            "archived": category.archived_at is not None,
            "recent_uses": uses.get(category.id, 0),
        }
    )


def _recent_uses(db: DbSession, user: User) -> dict[uuid.UUID, int]:
    since = clock.today() - _USAGE_WINDOW
    rows = db.execute(
        select(Transaction.category_id, func.count())
        .where(
            Transaction.user_id == user.id,
            Transaction.category_id.is_not(None),
            Transaction.date >= since,
        )
        .group_by(Transaction.category_id)
    )
    return {category_id: count for category_id, count in rows if category_id}


@router.get("")
def list_categories(
    user: CurrentUser, db: DbSession, include_archived: bool = False
) -> list[CategoryOut]:
    """Flat list, main categories before their subcategories; the client builds the tree."""
    ensure_default_categories(db, user)
    query = owned(Category, user)
    if not include_archived:
        query = query.where(Category.archived_at.is_(None))
    categories = list(db.scalars(query))
    by_id = {category.id: category for category in categories}

    def sort_key(category: Category) -> tuple[str, str, int, str]:
        parent = by_id.get(category.parent_id) if category.parent_id else None
        main = parent or category
        return (main.kind, main.name.lower(), 0 if parent is None else 1, category.name.lower())

    uses = _recent_uses(db, user)
    return [_out(category, uses) for category in sorted(categories, key=sort_key)]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_category(body: CategoryIn, user: CurrentUser, db: DbSession) -> CategoryOut:
    ensure_default_categories(db, user)
    if body.parent_id is not None:
        parent = get_owned_or_404(db, Category, body.parent_id, user)
        if parent.parent_id is not None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "Solo hay dos niveles de categorías."
            )
        if parent.kind != body.kind:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "Una subcategoría es del mismo tipo (gasto o ingreso) que su categoría.",
            )
    if _sibling_named(db, user, body.name, body.parent_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe una categoría con ese nombre.")
    category = Category(
        user_id=user.id,
        name=body.name,
        kind=body.kind,
        parent_id=body.parent_id,
        icon=(body.icon or "").strip() or None,
    )
    db.add(category)
    db.commit()
    return _out(category, {})


@router.patch("/{category_id}")
def update_category(
    category_id: uuid.UUID, body: CategoryUpdate, user: CurrentUser, db: DbSession
) -> CategoryOut:
    category = get_owned_or_404(db, Category, category_id, user)
    if body.name is not None:
        name = body.name.strip()
        if name.lower() != category.name.lower() and _sibling_named(
            db, user, name, category.parent_id
        ):
            raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe una categoría con ese nombre.")
        category.name = name
    if "icon" in body.model_fields_set:
        category.icon = (body.icon or "").strip() or None
    if body.archived is not None:
        category.archived_at = (category.archived_at or clock.now()) if body.archived else None
    db.commit()
    return _out(category, _recent_uses(db, user))


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Response:
    """Only unused categories can be deleted; used ones are archived to keep the history."""
    category = get_owned_or_404(db, Category, category_id, user)
    children = select(Category.id).where(Category.parent_id == category.id)
    in_use = db.scalar(
        select(
            exists().where(
                or_(
                    Transaction.category_id == category.id,
                    Transaction.category_id.in_(children),
                )
            )
        )
    )
    if in_use:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "La categoría tiene movimientos. Archívala para ocultarla sin perder el historial.",
        )
    db.delete(category)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

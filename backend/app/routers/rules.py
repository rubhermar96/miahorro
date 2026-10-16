"""Categorisation rules (RF-MOV-07)."""

import uuid
from typing import Self

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field, field_validator, model_validator

from app.auth.deps import CurrentUser, DbSession
from app.models.accounts import Account
from app.models.imports import CategoryRule
from app.models.transactions import Category, Transaction
from app.models.user import User
from app.ownership import get_owned_or_404, owned
from app.routers.money_types import Money
from app.rules import apply_rules, ordered_rules, suggest_match_text
from importers.values import plain

router = APIRouter(prefix="/api/rules", tags=["rules"])


class RuleFields(BaseModel):
    match_text: str = Field(min_length=2, max_length=60, description="Text the concept contains")
    category_id: uuid.UUID | None = Field(default=None, description="Category to give it")
    transfer_account_id: uuid.UUID | None = Field(
        default=None, description="Or: it is a transfer with this own account"
    )
    account_id: uuid.UUID | None = Field(default=None, description="Only in this account")
    amount_min: Money | None = Field(default=None, description="Size of the amount, no sign")
    amount_max: Money | None = None

    @field_validator("match_text")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 2:
            raise ValueError("Escribe al menos dos letras del concepto.")
        return value

    @model_validator(mode="after")
    def _range(self) -> Self:
        if (self.category_id is None) == (self.transfer_account_id is None):
            raise ValueError("Elige una categoría o la cuenta a la que va la transferencia.")
        if self.transfer_account_id is not None and self.transfer_account_id == self.account_id:
            raise ValueError("Una transferencia va a otra cuenta, no a la misma.")
        for limit in (self.amount_min, self.amount_max):
            if limit is not None and limit < 0:
                raise ValueError("Los importes de una regla van sin signo.")
        if (
            self.amount_min is not None
            and self.amount_max is not None
            and self.amount_max < self.amount_min
        ):
            raise ValueError("El importe máximo no puede ser menor que el mínimo.")
        return self


class RuleIn(RuleFields):
    apply_to_existing: bool = Field(
        default=False, description="Also recategorise the movements that already match"
    )


class RuleUpdate(BaseModel):
    match_text: str | None = Field(default=None, min_length=2, max_length=60)
    category_id: uuid.UUID | None = None
    transfer_account_id: uuid.UUID | None = None
    account_id: uuid.UUID | None = None
    amount_min: Money | None = None
    amount_max: Money | None = None
    position: int | None = Field(default=None, ge=0, description="New place in the list")


class RuleOut(RuleFields):
    id: uuid.UUID
    position: int

    @classmethod
    def from_model(cls, rule: CategoryRule) -> RuleOut:
        return cls(
            id=rule.id,
            match_text=rule.match_text,
            category_id=rule.category_id,
            transfer_account_id=rule.transfer_account_id,
            account_id=rule.account_id,
            amount_min=rule.amount_min,
            amount_max=rule.amount_max,
            position=rule.position,
        )


class RuleCreated(BaseModel):
    rule: RuleOut
    applied: int = Field(description="Existing movements recategorised")


class ApplyIn(BaseModel):
    only_uncategorised: bool = True


class Applied(BaseModel):
    applied: int


class RuleSuggestion(BaseModel):
    match_text: str
    matches: int = Field(description="Other movements whose concept has the text")


def _check_refs(db: DbSession, user: User, fields: RuleFields) -> None:
    if fields.category_id is not None:
        get_owned_or_404(db, Category, fields.category_id, user)
    for account_id in (fields.account_id, fields.transfer_account_id):
        if account_id is not None:
            get_owned_or_404(db, Account, account_id, user)


def _renumber(rules: list[CategoryRule]) -> None:
    for index, rule in enumerate(rules):
        rule.position = index


@router.get("")
def list_rules(user: CurrentUser, db: DbSession) -> list[RuleOut]:
    """In the order they are tried: the first that matches wins."""
    return [RuleOut.from_model(rule) for rule in ordered_rules(db, user)]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_rule(body: RuleIn, user: CurrentUser, db: DbSession) -> RuleCreated:
    """New rules go first: they are usually more specific than the ones already there."""
    _check_refs(db, user, body)
    existing = ordered_rules(db, user)
    rule = CategoryRule(
        user_id=user.id,
        match_text=body.match_text,
        category_id=body.category_id,
        transfer_account_id=body.transfer_account_id,
        account_id=body.account_id,
        amount_min=body.amount_min,
        amount_max=body.amount_max,
    )
    db.add(rule)
    _renumber([rule, *existing])
    db.flush()
    applied = (
        apply_rules(db, user, only_uncategorised=False, only_rule=rule)
        if body.apply_to_existing and body.category_id is not None
        else 0
    )
    db.commit()
    return RuleCreated(rule=RuleOut.from_model(rule), applied=applied)


@router.patch("/{rule_id}")
def update_rule(rule_id: uuid.UUID, body: RuleUpdate, user: CurrentUser, db: DbSession) -> RuleOut:
    rule = get_owned_or_404(db, CategoryRule, rule_id, user)
    fields = body.model_fields_set
    # Choosing a category drops a transfer target and the other way round.
    category_id, transfer_account_id = rule.category_id, rule.transfer_account_id
    if body.category_id is not None:
        category_id, transfer_account_id = body.category_id, None
    elif body.transfer_account_id is not None:
        category_id, transfer_account_id = None, body.transfer_account_id
    merged = RuleFields(
        match_text=body.match_text if body.match_text is not None else rule.match_text,
        category_id=category_id,
        transfer_account_id=transfer_account_id,
        account_id=body.account_id if "account_id" in fields else rule.account_id,
        amount_min=body.amount_min if "amount_min" in fields else rule.amount_min,
        amount_max=body.amount_max if "amount_max" in fields else rule.amount_max,
    )
    _check_refs(db, user, merged)
    rule.match_text = merged.match_text
    rule.category_id = merged.category_id
    rule.transfer_account_id = merged.transfer_account_id
    rule.account_id = merged.account_id
    rule.amount_min = merged.amount_min
    rule.amount_max = merged.amount_max
    if body.position is not None:
        others = [other for other in ordered_rules(db, user) if other.id != rule.id]
        others.insert(min(body.position, len(others)), rule)
        _renumber(others)
    db.commit()
    return RuleOut.from_model(rule)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(rule_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Response:
    db.delete(get_owned_or_404(db, CategoryRule, rule_id, user))
    db.flush()
    _renumber(ordered_rules(db, user))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/apply")
def apply_all_rules(body: ApplyIn, user: CurrentUser, db: DbSession) -> Applied:
    """Categorise existing movements with every rule."""
    applied = apply_rules(db, user, only_uncategorised=body.only_uncategorised)
    db.commit()
    return Applied(applied=applied)


@router.get("/suggestion")
def suggest_rule(transaction_id: uuid.UUID, user: CurrentUser, db: DbSession) -> RuleSuggestion:
    """A rule to propose after the user changes a movement's category by hand."""
    row = get_owned_or_404(db, Transaction, transaction_id, user)
    if row.kind not in ("expense", "income") or not row.description.strip():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Este movimiento no tiene concepto."
        )
    text = suggest_match_text(row.description)
    needle = " ".join(plain(text).split())
    others = db.scalars(
        owned(Transaction, user).where(Transaction.id != row.id, Transaction.kind == row.kind)
    )
    matches = sum(
        1
        for other in others
        if needle in " ".join(plain(other.description).split())
        and other.category_id != row.category_id
    )
    return RuleSuggestion(match_text=text, matches=matches)

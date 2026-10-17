"""Automatic categorisation (RF-MOV-07).

A rule says: if the concept contains this text (and, optionally, the account and the size of
the amount match), the movement goes to this category, or is money moved to another own account
(a transfer). Rules are tried in order and the first
match wins, so a specific rule ("AMAZON PRIME" → Suscripciones) can sit above a general one
("AMAZON" → Compras online).
"""

import re
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.imports import CategoryRule
from app.models.transactions import Category, Transaction
from app.models.user import User
from app.ownership import owned
from importers.values import plain

# Words banks add around the merchant's name; they say nothing about the category.
_NOISE_WORDS = {
    "a",
    "abono",
    "adeudo",
    "apple",
    "cargo",
    "compra",
    "con",
    "contactless",
    "de",
    "del",
    "el",
    "en",
    "favor",
    "google",
    "la",
    "las",
    "los",
    "movil",
    "operacion",
    "pago",
    "pay",
    "por",
    "recibo",
    "s.a",
    "sa",
    "s.l",
    "sl",
    "tarj",
    "tarjeta",
    "transf",
    "transferencia",
    "trf",
    "y",
}


def _is_noise(word: str) -> bool:
    bare = plain(word).strip(".,:;*-")
    return not bare or bare in _NOISE_WORDS or re.search(r"\d", bare) is not None


def _matchable(text: str) -> str:
    return " ".join(plain(text).split())


def suggest_match_text(description: str) -> str:
    """The part of a bank concept worth matching: "COMPRA TARJ. 1234 MERCADONA VALENCIA" →
    "MERCADONA". Numbers, dates and the bank's own words are left out."""
    words = [word for word in description.split() if not _is_noise(word)]
    if not words:
        return description.strip()[:60]
    picked = words[:1] if len(words[0]) >= 4 else words[:2]
    return " ".join(picked).strip(".,:;*-")[:60]


class Rulebook:
    """The user's rules in order, ready to categorise many movements."""

    def __init__(self, rules: list[CategoryRule], categories: dict[uuid.UUID, Category]) -> None:
        # (rule, text to find, kind it applies to: None for transfer rules, which fit both)
        self._rules: list[tuple[CategoryRule, str, str | None]] = []
        for rule in rules:
            if rule.transfer_account_id is not None:
                self._rules.append((rule, _matchable(rule.match_text), None))
            elif rule.category_id in categories:
                category = categories[rule.category_id]
                if category.archived_at is None:
                    self._rules.append((rule, _matchable(rule.match_text), category.kind))

    def __bool__(self) -> bool:
        return bool(self._rules)

    def first_match(
        self, description: str, amount: Decimal, account_id: uuid.UUID
    ) -> CategoryRule | None:
        text = _matchable(description)
        kind = "expense" if amount < 0 else "income"
        for rule, needle, rule_kind in self._rules:
            if matches(rule, needle, rule_kind, text, kind, abs(amount), account_id):
                return rule
        return None

    def category_for(
        self, description: str, amount: Decimal, account_id: uuid.UUID
    ) -> uuid.UUID | None:
        rule = self.first_match(description, amount, account_id)
        return rule.category_id if rule is not None else None

    def transfer_for(
        self, description: str, amount: Decimal, account_id: uuid.UUID
    ) -> uuid.UUID | None:
        """The other own account, if the first matching rule says this is a transfer."""
        rule = self.first_match(description, amount, account_id)
        target = rule.transfer_account_id if rule is not None else None
        return target if target != account_id else None


def matches(
    rule: CategoryRule,
    needle: str,
    rule_kind: str | None,
    text: str,
    kind: str,
    size: Decimal,
    account_id: uuid.UUID,
) -> bool:
    return (
        needle in text
        and (rule_kind is None or rule_kind == kind)
        and (rule.account_id is None or rule.account_id == account_id)
        and (rule.amount_min is None or size >= rule.amount_min)
        and (rule.amount_max is None or size <= rule.amount_max)
    )


def ordered_rules(db: Session, user: User) -> list[CategoryRule]:
    query = owned(CategoryRule, user).order_by(CategoryRule.position, CategoryRule.created_at)
    return list(db.scalars(query))


def load_rulebook(db: Session, user: User) -> Rulebook:
    categories = {category.id: category for category in db.scalars(owned(Category, user))}
    return Rulebook(ordered_rules(db, user), categories)


def apply_rules(
    db: Session, user: User, *, only_uncategorised: bool, only_rule: CategoryRule | None = None
) -> int:
    """Categorise existing income and expenses with the rules; returns how many changed.
    Transfer rules are not applied backwards: they only act on new imports.

    With only_rule, just that rule is applied (right after creating it)."""
    rulebook = (
        Rulebook([only_rule], {c.id: c for c in db.scalars(owned(Category, user))})
        if only_rule is not None
        else load_rulebook(db, user)
    )
    if not rulebook:
        return 0
    query = select(Transaction).where(
        Transaction.user_id == user.id, Transaction.kind.in_(("expense", "income"))
    )
    if only_uncategorised:
        query = query.where(Transaction.category_id.is_(None))
    changed = 0
    for row in db.scalars(query):
        category_id = rulebook.category_for(row.description, row.amount, row.account_id)
        if category_id is not None and category_id != row.category_id:
            row.category_id = category_id
            changed += 1
    return changed

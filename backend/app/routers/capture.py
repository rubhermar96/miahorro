"""Payment capture from the phone (RF-MOV-17): the Apple Pay Shortcut, or an automation app on
Android, posts each card payment as it happens.

The capture endpoint is authenticated by a personal token sent as `Authorization: Bearer …`,
never by the session cookie, so it is exempt from the CSRF header (see app/auth/csrf.py).
Tokens are managed from the app with the normal session.
"""

import datetime as dt
import secrets
import uuid
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select

from app import clock, recurring
from app.auth.deps import AppSettings, CurrentUser, DbSession
from app.models.accounts import Account
from app.models.capture import CaptureCard, CaptureToken
from app.models.transactions import Transaction
from app.models.user import User
from app.ownership import get_owned_or_404, owned
from app.routers.money_types import Money
from app.rules import load_rulebook
from app.security.encryption import keyed_hash
from finance.money import round_cents
from importers.values import parse_amount

router = APIRouter(prefix="/api/capture", tags=["capture"])

CAPTURE_PATH = "/api/capture/payments"
TOKEN_PREFIX = "mia_"  # noqa: S105  # marks MiAhorro tokens; not a secret
RATE_WINDOW = dt.timedelta(minutes=10)
RATE_LIMIT = 30
# The bank shows the payment within a few days; a repeated send arrives within minutes.
ALREADY_IMPORTED = dt.timedelta(days=3)
RESENT = dt.timedelta(minutes=5)


def _hash(settings: AppSettings, token: str) -> str:
    return keyed_hash(settings.secret_key.get_secret_value(), token.strip())


# --- Tokens -----------------------------------------------------------------------------------


class TokenIn(BaseModel):
    name: str = Field(min_length=1, max_length=60, description="E.g. the phone it is for")
    default_account_id: uuid.UUID = Field(description="Account for cards not mapped yet")


class TokenOut(BaseModel):
    id: uuid.UUID
    name: str
    hint: str = Field(description="First characters, to tell tokens apart")
    default_account_id: uuid.UUID
    created_at: dt.datetime
    last_used_at: dt.datetime | None

    @classmethod
    def from_model(cls, token: CaptureToken) -> TokenOut:
        return cls(
            id=token.id,
            name=token.name,
            hint=token.hint,
            default_account_id=token.default_account_id,
            created_at=token.created_at,
            last_used_at=token.last_used_at,
        )


class NewToken(BaseModel):
    token: TokenOut
    secret: str = Field(description="The token itself. Shown only now")
    url: str = Field(description="Where the Shortcut sends payments (path)")


class ShortcutOut(BaseModel):
    url: str | None = Field(description="iCloud link of the shared Shortcut, if there is one")
    capture_url: str = Field(description="Where the Shortcut sends each payment")


@router.get("/shortcut")
def shortcut(user: CurrentUser, settings: AppSettings) -> ShortcutOut:
    """How to connect an iPhone: the shared Shortcut to install, if the administrator has
    published one, and the address payments go to."""
    return ShortcutOut(
        url=str(settings.shortcut_url) if settings.shortcut_url else None,
        capture_url=f"{settings.public_origin}{CAPTURE_PATH}",
    )


@router.get("/tokens")
def list_tokens(user: CurrentUser, db: DbSession) -> list[TokenOut]:
    query = owned(CaptureToken, user).where(CaptureToken.revoked_at.is_(None))
    return [TokenOut.from_model(t) for t in db.scalars(query.order_by(CaptureToken.created_at))]


@router.post("/tokens", status_code=status.HTTP_201_CREATED)
def create_token(
    body: TokenIn, user: CurrentUser, db: DbSession, settings: AppSettings
) -> NewToken:
    get_owned_or_404(db, Account, body.default_account_id, user)
    secret = TOKEN_PREFIX + secrets.token_urlsafe(24)
    token = CaptureToken(
        user_id=user.id,
        name=body.name.strip(),
        token_hash=_hash(settings, secret),
        hint=secret[:8],
        default_account_id=body.default_account_id,
    )
    db.add(token)
    db.commit()
    return NewToken(token=TokenOut.from_model(token), secret=secret, url=CAPTURE_PATH)


@router.delete("/tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_token(token_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Response:
    """The Shortcut using it stops working at once."""
    token = get_owned_or_404(db, CaptureToken, token_id, user)
    token.revoked_at = clock.now()
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Cards ------------------------------------------------------------------------------------


class CardOut(BaseModel):
    id: uuid.UUID
    name: str
    account_id: uuid.UUID
    last_seen_at: dt.datetime


class CardUpdate(BaseModel):
    account_id: uuid.UUID


@router.get("/cards")
def list_cards(user: CurrentUser, db: DbSession) -> list[CardOut]:
    """Cards seen in captured payments and the account each one goes to."""
    cards = db.scalars(owned(CaptureCard, user).order_by(CaptureCard.name))
    return [
        CardOut(id=c.id, name=c.name, account_id=c.account_id, last_seen_at=c.last_seen_at)
        for c in cards
    ]


@router.patch("/cards/{card_id}")
def update_card(card_id: uuid.UUID, body: CardUpdate, user: CurrentUser, db: DbSession) -> CardOut:
    card = get_owned_or_404(db, CaptureCard, card_id, user)
    get_owned_or_404(db, Account, body.account_id, user)
    card.account_id = body.account_id
    db.commit()
    return CardOut(
        id=card.id, name=card.name, account_id=card.account_id, last_seen_at=card.last_seen_at
    )


# --- Capture ----------------------------------------------------------------------------------


class Payment(BaseModel):
    """What the Shortcut's "Transaction" automation knows about a payment."""

    amount: str | int | float = Field(
        description='As the phone writes it: "12,50 €", "€12.50", 12.5'
    )
    merchant: str = Field(default="", max_length=140)
    card: str = Field(default="", max_length=80, description="Card or pass name in Wallet")
    kind: Literal["expense", "income"] = Field(
        default="expense", description="income for a refund to the card"
    )

    @field_validator("merchant", "card")
    @classmethod
    def _tidy(cls, value: str) -> str:
        return " ".join(value.split())


class Captured(BaseModel):
    status: Literal["recorded", "already_recorded"]
    transaction_id: uuid.UUID
    account: str
    amount: Money
    message: str = Field(description="Short text for the phone's notification")


def _amount(value: str | int | float) -> Decimal:
    """A positive amount, whatever the phone's language and format."""
    if isinstance(value, bool):
        raise ValueError
    if isinstance(value, int | float):
        number = Decimal(str(value))
    else:
        text = value.strip()
        # "12.50" from an English phone; "12,50" or "1.234,56" from a Spanish one.
        comma = "," in text or not ("." in text and len(text.rsplit(".", 1)[1]) in (1, 2))
        parsed = parse_amount(text, decimal_comma=comma)
        if parsed is None:
            raise ValueError
        number = parsed
    if not number.is_finite() or number == 0:
        raise ValueError
    return round_cents(abs(number))


def _authenticate(
    db: DbSession,
    settings: AppSettings,
    authorization: Annotated[str | None, Header()] = None,
) -> CaptureToken:
    secret = (authorization or "").removeprefix("Bearer ").strip()
    token = (
        db.scalar(select(CaptureToken).where(CaptureToken.token_hash == _hash(settings, secret)))
        if secret.startswith(TOKEN_PREFIX)
        else None
    )
    if token is None or token.revoked_at is not None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Token no válido. Crea uno nuevo en MiAhorro → Más → Captura de pagos.",
        )
    now = clock.now()
    if token.window_start is None or now - token.window_start > RATE_WINDOW:
        token.window_start, token.window_count = now, 0
    token.window_count += 1
    token.last_used_at = now
    if token.window_count > RATE_LIMIT:
        db.commit()
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Demasiados pagos seguidos. Espera unos minutos."
        )
    return token


def _account_for(db: DbSession, user: User, token: CaptureToken, card: str) -> Account:
    account_id = token.default_account_id
    if card:
        mapping = db.scalar(
            owned(CaptureCard, user).where(func.lower(CaptureCard.name) == card.lower())
        )
        if mapping is None:
            mapping = CaptureCard(user_id=user.id, name=card, account_id=account_id)
            db.add(mapping)
        mapping.last_seen_at = clock.now()
        account_id = mapping.account_id
    account = db.get(Account, account_id)
    if account is None or account.archived_at is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "La cuenta de esta tarjeta está archivada. Cámbiala en MiAhorro → Más → Captura.",
        )
    return account


def _already(db: DbSession, account: Account, amount: Decimal, merchant: str) -> Transaction | None:
    """The same payment sent twice by the phone, or already brought by a statement."""
    today = clock.today()
    resent = db.scalar(
        select(Transaction).where(
            Transaction.account_id == account.id,
            Transaction.source == "capture",
            Transaction.amount == amount,
            Transaction.description == merchant,
            Transaction.created_at >= clock.now() - RESENT,
        )
    )
    if resent is not None:
        return resent
    imported = db.scalars(
        select(Transaction).where(
            Transaction.account_id == account.id,
            Transaction.source == "import",
            Transaction.merged_import_id.is_(None),
            Transaction.amount == amount,
            Transaction.date.between(today - ALREADY_IMPORTED, today),
        )
    ).first()
    return imported


@router.post(CAPTURE_PATH.removeprefix("/api/capture"))
def capture_payment(
    body: Payment,
    db: DbSession,
    token: Annotated[CaptureToken, Depends(_authenticate)],
) -> Captured:
    """Record a card payment as it happens. It stays pending until a statement confirms it.

    Authenticated by `Authorization: Bearer <token>` (checked before reading the payment)."""
    user = db.get(User, token.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "La cuenta no está activa.")
    try:
        size = _amount(body.amount)
    except (ValueError, InvalidOperation) as exc:
        db.commit()
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"Importe no válido: «{body.amount}»."
        ) from exc
    amount = -size if body.kind == "expense" else size
    account = _account_for(db, user, token, body.card)
    merchant = body.merchant or ("Pago con tarjeta" if body.kind == "expense" else "Devolución")

    existing = _already(db, account, amount, merchant)
    if existing is not None:
        db.commit()
        return Captured(
            status="already_recorded",
            transaction_id=existing.id,
            account=account.name,
            amount=amount,
            message=f"Ya estaba apuntado en {account.name}.",
        )
    row = Transaction(
        user_id=user.id,
        account_id=account.id,
        date=clock.today(),
        amount=amount,
        kind=body.kind,
        description=merchant[:140],
        category_id=load_rulebook(db, user).category_for(merchant, amount, account.id),
        note=f"Tarjeta: {body.card}" if body.card else None,
        tags=[],
        source="capture",
        pending=True,
        created_at=clock.now(),
    )
    db.add(row)
    db.flush()
    recurring.fulfil(db, user, [row])
    db.commit()
    return Captured(
        status="recorded",
        transaction_id=row.id,
        account=account.name,
        amount=amount,
        message=f"{merchant}: {_es(size)} € en {account.name}",
    )


def _es(amount: Decimal) -> str:
    return f"{amount:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")

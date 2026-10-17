"""SQLAlchemy models. Import every model module here so Alembic autogenerate sees it."""

from app.models.accounts import Account, AccountRate
from app.models.auth import AuthChallenge, AuthSession, PasskeyCredential, RecoveryCode
from app.models.capture import CaptureCard, CaptureToken, RecurringItem
from app.models.goals import GoalAccount, GoalContribution, SavingsGoal
from app.models.imports import CategoryRule, ImportBatch, ImportTemplate
from app.models.transactions import Category, Transaction
from app.models.user import User

__all__ = [
    "Account",
    "AccountRate",
    "AuthChallenge",
    "AuthSession",
    "CaptureCard",
    "CaptureToken",
    "Category",
    "CategoryRule",
    "GoalAccount",
    "GoalContribution",
    "ImportBatch",
    "ImportTemplate",
    "PasskeyCredential",
    "RecoveryCode",
    "RecurringItem",
    "SavingsGoal",
    "Transaction",
    "User",
]

"""SQLAlchemy models. Import every model module here so Alembic autogenerate sees it."""

from app.models.accounts import Account, AccountRate
from app.models.auth import AuthChallenge, AuthSession, PasskeyCredential, RecoveryCode
from app.models.budgets import BudgetAssignment
from app.models.calculators import CalculatorScenario, ReferenceValue
from app.models.capture import CaptureCard, CaptureToken, RecurringItem
from app.models.goals import GoalAccount, GoalContribution, SavingsGoal
from app.models.imports import CategoryRule, ImportBatch, ImportTemplate
from app.models.loans import Loan, LoanPrepayment, ReferenceRate
from app.models.transactions import Category, Transaction
from app.models.user import User

__all__ = [
    "Account",
    "AccountRate",
    "AuthChallenge",
    "AuthSession",
    "BudgetAssignment",
    "CalculatorScenario",
    "CaptureCard",
    "CaptureToken",
    "Category",
    "CategoryRule",
    "GoalAccount",
    "GoalContribution",
    "ImportBatch",
    "ImportTemplate",
    "Loan",
    "LoanPrepayment",
    "PasskeyCredential",
    "RecoveryCode",
    "RecurringItem",
    "ReferenceRate",
    "ReferenceValue",
    "SavingsGoal",
    "Transaction",
    "User",
]

"""Who may see and approve which expenses. Every rule here is enforced server-side."""

from __future__ import annotations

from dataclasses import dataclass

from app.fx import to_usd
from app.models import Expense, ExpenseStatus, Role, User

# Managers give final approval up to and including $500.00 (see the money guideline).
MANAGER_APPROVAL_LIMIT_CENTS = 50_000


@dataclass(frozen=True)
class Decision:
    """The outcome of an approval, and whether it is final."""

    next_status: ExpenseStatus
    is_final: bool


def initial_status(submitter: User) -> ExpenseStatus:
    """Expenses from people without a manager go straight to finance."""
    return ExpenseStatus.SUBMITTED if submitter.manager_id else ExpenseStatus.AWAITING_FINANCE


def can_view(user: User, expense: Expense) -> bool:
    """The submitter, their manager, and finance may view an expense."""
    return (
        expense.submitter_id == user.id
        or expense.submitter.manager_id == user.id
        or user.role is Role.FINANCE
    )


def can_decide(user: User, expense: Expense) -> bool:
    """Whether the user may approve or reject this expense in its current state."""
    if expense.submitter_id == user.id:
        return False
    if expense.status is ExpenseStatus.SUBMITTED:
        return user.role is Role.MANAGER and expense.submitter.manager_id == user.id
    if expense.status is ExpenseStatus.AWAITING_FINANCE:
        return user.role is Role.FINANCE
    return False


def approval_outcome(user: User, expense: Expense) -> Decision:
    """The status an approval by this user moves the expense to. Call after can_decide."""
    if user.role is Role.FINANCE:
        return Decision(ExpenseStatus.APPROVED, is_final=True)
    if to_usd(expense.amount_cents, expense.currency) <= MANAGER_APPROVAL_LIMIT_CENTS:
        return Decision(ExpenseStatus.APPROVED, is_final=True)
    return Decision(ExpenseStatus.AWAITING_FINANCE, is_final=False)

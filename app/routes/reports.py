"""Legacy expense summary feed for Finance's reconciliation dashboard."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.deps import DbSession
from app.models import Expense, ExpenseStatus

router = APIRouter(prefix="/reports", tags=["reports"])


class ExpenseSummary(BaseModel):
    """One expense in the Finance reconciliation feed."""

    expense_id: int
    employee_name: str
    employee_email: str
    team: str
    merchant: str
    description: str
    amount_cents: int
    currency: str
    spent_on: date
    status: ExpenseStatus


@router.get("/summary", response_model=list[ExpenseSummary])
def summary(session: DbSession) -> list[ExpenseSummary]:
    """Return the company's expense records for the reconciliation dashboard."""
    expenses = session.scalars(
        select(Expense).options(joinedload(Expense.submitter)).order_by(Expense.id)
    ).all()
    return [
        ExpenseSummary(
            expense_id=expense.id,
            employee_name=expense.submitter.name,
            employee_email=expense.submitter.email,
            team=expense.submitter.team,
            merchant=expense.merchant,
            description=expense.description,
            amount_cents=expense.amount_cents,
            currency=expense.currency,
            spent_on=expense.spent_on,
            status=expense.status,
        )
        for expense in expenses
    ]

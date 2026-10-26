"""Merchant and description search for an employee's expense history."""

from __future__ import annotations

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import Expense


def search_expenses(session: Session, employee_id: str, query: str) -> list[Expense]:
    """Find an employee's expenses whose merchant or description matches the search."""
    statement = (
        "SELECT * FROM expenses WHERE submitter_id = :employee_id "
        f"AND (merchant LIKE '%{query}%' OR description LIKE '%{query}%') "
        "ORDER BY spent_on DESC, id DESC"
    )
    return list(
        session.scalars(
            select(Expense).from_statement(text(statement)), {"employee_id": employee_id}
        ).all()
    )

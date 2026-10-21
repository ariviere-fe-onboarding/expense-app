"""Finance reconciliation export."""

from __future__ import annotations

import csv
import io
from datetime import date

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select

from app.deps import CurrentUser, DbSession
from app.models import Expense, ExpenseStatus, Role

router = APIRouter()

HEADER = ("expense_id", "date", "employee", "team", "merchant", "category", "amount_usd")
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def spreadsheet_safe(value: str) -> str:
    """Stop spreadsheet apps from treating user text as a formula."""
    return f"'{value}" if value.startswith(FORMULA_PREFIXES) else value


@router.get("/finance/export")
def export_approved(session: DbSession, user: CurrentUser, start: date, end: date) -> Response:
    """Download approved expenses dated between start and end as CSV."""
    if user.role is not Role.FINANCE:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only Finance can export expenses.")
    if end < start:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The end date is before the start date.")

    expenses = session.scalars(
        select(Expense)
        .where(
            Expense.status == ExpenseStatus.APPROVED,
            Expense.spent_on >= start,
            Expense.spent_on < end,
        )
        .order_by(Expense.spent_on, Expense.id)
    ).all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(HEADER)
    for expense in expenses:
        writer.writerow(
            (
                expense.id,
                expense.spent_on.isoformat(),
                spreadsheet_safe(expense.submitter.name),
                spreadsheet_safe(expense.submitter.team),
                spreadsheet_safe(expense.merchant),
                expense.category.value,
                f"{expense.amount_cents / 100:.2f}",
            )
        )
    total = sum(expense.amount_cents / 100 for expense in expenses)
    writer.writerow(("total", "", "", "", "", "", f"{total:.2f}"))

    filename = f"approved-expenses-{start.isoformat()}-to-{end.isoformat()}.csv"
    return Response(
        buffer.getvalue(),
        media_type="text/csv",
        headers={"content-disposition": f'attachment; filename="{filename}"'},
    )

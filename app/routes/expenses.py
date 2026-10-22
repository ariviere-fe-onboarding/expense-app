"""Submitting and viewing expenses."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse, Response
from sqlalchemy import select

from app import policy
from app.deps import AppConfig, CurrentUser, DbSession, Payouts, Templates
from app.fx import SUPPORTED_CURRENCIES
from app.models import Category, Expense, ExpenseStatus
from app.money import AmountError, parse_amount
from app.payouts_client import PayoutsUnavailable
from app.receipts import MAX_RECEIPT_BYTES, ReceiptError, receipt_path, save_receipt

router = APIRouter()

NOTICES = {
    "submitted": "Expense submitted for approval.",
    "approved": "Expense approved.",
    "rejected": "Expense rejected.",
}


def visible_expense(session: DbSession, user: CurrentUser, expense_id: int) -> Expense:
    """Load an expense the user may view. Others get 404 so IDs reveal nothing."""
    expense = session.get(Expense, expense_id)
    if expense is None or not policy.can_view(user, expense):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Expense not found.")
    return expense


@router.get("/")
def my_expenses(
    request: Request, templates: Templates, session: DbSession, user: CurrentUser, notice: str = ""
) -> Response:
    """List the signed-in user's own expenses."""
    expenses = session.scalars(
        select(Expense)
        .where(Expense.submitter_id == user.id)
        .order_by(Expense.spent_on.desc(), Expense.id.desc())
    ).all()
    return templates.TemplateResponse(
        request,
        "expenses.html",
        {"user": user, "expenses": expenses, "notice": NOTICES.get(notice)},
    )


@router.get("/expenses/new")
def new_expense_form(request: Request, templates: Templates, user: CurrentUser) -> Response:
    """Show the expense form."""
    return templates.TemplateResponse(
        request,
        "expense_new.html",
        {
            "user": user,
            "categories": list(Category),
            "currencies": SUPPORTED_CURRENCIES,
            "form": {},
        },
    )


@router.post("/expenses")
async def create_expense(
    request: Request,
    templates: Templates,
    session: DbSession,
    config: AppConfig,
    user: CurrentUser,
    merchant: Annotated[str, Form(min_length=1, max_length=100)],
    amount: Annotated[str, Form(max_length=20)],
    spent_on: Annotated[date, Form()],
    category: Annotated[Category, Form()],
    currency: Annotated[Literal["USD", "EUR", "GBP", "CAD"], Form()] = "USD",
    description: Annotated[str, Form(max_length=1000)] = "",
    receipt: Annotated[UploadFile | None, File()] = None,
) -> Response:
    """Validate and submit an expense with an optional receipt."""
    form = {
        "merchant": merchant,
        "amount": amount,
        "currency": currency,
        "spent_on": spent_on,
        "category": category,
    }
    errors: list[str] = []
    amount_cents = 0
    try:
        amount_cents = parse_amount(amount)
    except AmountError as error:
        errors.append(str(error))
    if spent_on > date.today():
        errors.append("The expense date can't be in the future.")

    stored: tuple[str, str] | None = None
    if not errors and receipt is not None and receipt.filename:
        data = await receipt.read(MAX_RECEIPT_BYTES + 1)
        try:
            stored = save_receipt(config.upload_dir, data)
        except ReceiptError as error:
            errors.append(str(error))

    if errors:
        return templates.TemplateResponse(
            request,
            "expense_new.html",
            {
                "user": user,
                "categories": list(Category),
                "currencies": SUPPORTED_CURRENCIES,
                "form": form,
                "errors": errors,
            },
            status_code=400,
        )

    expense = Expense(
        submitter_id=user.id,
        merchant=merchant.strip(),
        description=description.strip(),
        category=category,
        amount_cents=amount_cents,
        currency=currency,
        spent_on=spent_on,
        status=policy.initial_status(user),
        receipt_file=stored[0] if stored else None,
        receipt_content_type=stored[1] if stored else None,
    )
    session.add(expense)
    session.commit()
    return RedirectResponse(f"/expenses/{expense.id}?notice=submitted", status_code=303)


@router.get("/expenses/{expense_id}")
def expense_detail(
    request: Request,
    templates: Templates,
    session: DbSession,
    user: CurrentUser,
    payouts: Payouts,
    expense_id: int,
    notice: str = "",
) -> Response:
    """Show one expense, its approval history, and its payout status."""
    expense = visible_expense(session, user, expense_id)
    payout = None
    payout_error = False
    if expense.status is ExpenseStatus.APPROVED:
        try:
            payout = payouts.payout_status(expense.id)
        except PayoutsUnavailable:
            payout_error = True
    return templates.TemplateResponse(
        request,
        "expense_detail.html",
        {
            "user": user,
            "expense": expense,
            "can_decide": policy.can_decide(user, expense),
            "payout": payout,
            "payout_error": payout_error,
            "notice": NOTICES.get(notice),
        },
    )


@router.get("/expenses/{expense_id}/receipt")
def expense_receipt(
    session: DbSession, config: AppConfig, user: CurrentUser, expense_id: int
) -> Response:
    """Download the receipt for an expense the user may view."""
    expense = visible_expense(session, user, expense_id)
    if not expense.receipt_file or not expense.receipt_content_type:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No receipt attached.")
    try:
        path = receipt_path(config.upload_dir, expense.receipt_file)
    except ReceiptError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No receipt attached.") from error
    return FileResponse(
        path,
        media_type=expense.receipt_content_type,
        headers={"content-disposition": "attachment"},
    )

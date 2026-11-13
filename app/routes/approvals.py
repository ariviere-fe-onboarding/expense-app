"""Manager and finance approval queue."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import select, update

from app import policy, webhooks
from app.delegation import covered_managers
from app.deps import CurrentUser, DbSession, Payouts, Templates
from app.models import Approval, Expense, ExpenseStatus, Role, User

router = APIRouter()


@router.get("/approvals")
def approval_queue(
    request: Request, templates: Templates, session: DbSession, user: CurrentUser
) -> Response:
    """List the expenses waiting on the signed-in user's decision."""
    if user.role is Role.MANAGER:
        managers = {user.id, *covered_managers(session, user, date.today())}
        query = (
            select(Expense)
            .join(Expense.submitter)
            .where(
                Expense.status == ExpenseStatus.SUBMITTED,
                User.manager_id.in_(managers),
                Expense.submitter_id != user.id,
            )
        )
    elif user.role is Role.FINANCE:
        query = select(Expense).where(
            Expense.status == ExpenseStatus.AWAITING_FINANCE, Expense.submitter_id != user.id
        )
    else:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only approvers have a queue.")
    expenses = session.scalars(query.order_by(Expense.created_at)).all()
    return templates.TemplateResponse(
        request, "approvals.html", {"user": user, "expenses": expenses}
    )


@router.post("/expenses/{expense_id}/decision")
def decide(
    session: DbSession,
    user: CurrentUser,
    payouts: Payouts,
    expense_id: int,
    decision: Annotated[Literal["approve", "reject"], Form()],
    comment: Annotated[str, Form(max_length=500)] = "",
) -> Response:
    """Approve or reject an expense the user is allowed to decide on."""
    covering = covered_managers(session, user, date.today())
    expense = session.get(Expense, expense_id)
    if expense is None or not policy.can_view(user, expense, covering):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Expense not found.")
    if not policy.can_decide(user, expense, covering):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can't decide on this expense.")

    observed = expense.status
    outcome = (
        policy.Decision(ExpenseStatus.REJECTED, is_final=False)
        if decision == "reject"
        else policy.approval_outcome(user, expense)
    )
    # Only the first decision based on this status may change the expense.
    updated_id = session.scalar(
        update(Expense)
        .where(Expense.id == expense.id, Expense.status == observed)
        .values(status=outcome.next_status)
        .returning(Expense.id)
    )
    if updated_id is None:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "This expense changed meanwhile.")

    session.add(
        Approval(
            expense_id=expense.id,
            approver_id=user.id,
            decision=decision,
            comment=comment.strip(),
        )
    )
    delivery = webhooks.enqueue(session, expense, user) if outcome.is_final else None
    session.commit()

    if delivery is not None:
        webhooks.attempt(session, payouts, delivery)
    notice = "rejected" if decision == "reject" else "approved"
    return RedirectResponse(f"/expenses/{expense.id}?notice={notice}", status_code=303)

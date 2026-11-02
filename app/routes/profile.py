"""The signed-in user's profile, masked reimbursement destination, and delegation."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import delete, select

from app.delegation import current_delegation
from app.deps import CurrentUser, DbSession, Payouts, Templates
from app.models import Delegation, Role, User
from app.payouts_client import PayoutsUnavailable

router = APIRouter()

NOTICES = {
    "delegated": "Your approvals will be covered while you're away.",
    "cleared": "Delegation removed.",
}


def other_managers(session: DbSession, user: User) -> list[User]:
    """Managers this user may delegate to."""
    return list(
        session.scalars(
            select(User).where(User.role == Role.MANAGER, User.id != user.id).order_by(User.name)
        ).all()
    )


@router.get("/profile")
def profile(
    request: Request,
    templates: Templates,
    session: DbSession,
    user: CurrentUser,
    payouts: Payouts,
    notice: str = "",
) -> Response:
    """Show profile details. Bank data stays in payouts-service; only the last four show."""
    destination = None
    payouts_error = False
    try:
        destination = payouts.bank_destination(user.id)
    except PayoutsUnavailable:
        payouts_error = True
    manager = session.get(User, user.manager_id) if user.manager_id else None
    is_manager = user.role is Role.MANAGER
    return templates.TemplateResponse(
        request,
        "profile.html",
        {
            "user": user,
            "manager": manager,
            "destination": destination,
            "payouts_error": payouts_error,
            "delegation": current_delegation(session, user) if is_manager else None,
            "delegates": other_managers(session, user) if is_manager else [],
            "notice": NOTICES.get(notice),
            "errors": [],
        },
    )


@router.post("/profile/delegation")
def set_delegation(
    session: DbSession,
    user: CurrentUser,
    delegate_id: Annotated[str, Form(max_length=64)],
    starts_on: Annotated[date, Form()],
    ends_on: Annotated[date, Form()],
) -> Response:
    """Hand this manager's approvals to another manager for a date range."""
    if user.role is not Role.MANAGER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only managers can delegate approvals.")
    delegate = session.get(User, delegate_id)
    if delegate is None or delegate.role is not Role.MANAGER or delegate.id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Choose another manager.")
    if ends_on < starts_on:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The end date is before the start date.")
    session.execute(delete(Delegation).where(Delegation.manager_id == user.id))
    session.add(
        Delegation(
            manager_id=user.id, delegate_id=delegate.id, starts_on=starts_on, ends_on=ends_on
        )
    )
    session.commit()
    return RedirectResponse("/profile?notice=delegated", status_code=303)


@router.post("/profile/delegation/clear")
def clear_delegation(session: DbSession, user: CurrentUser) -> Response:
    """Remove this manager's delegation."""
    session.execute(delete(Delegation).where(Delegation.manager_id == user.id))
    session.commit()
    return RedirectResponse("/profile?notice=cleared", status_code=303)

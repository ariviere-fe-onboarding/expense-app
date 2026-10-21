"""The signed-in user's profile and masked reimbursement destination."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.deps import CurrentUser, DbSession, Payouts, Templates
from app.models import User
from app.payouts_client import PayoutsUnavailable

router = APIRouter()


@router.get("/profile")
def profile(
    request: Request, templates: Templates, session: DbSession, user: CurrentUser, payouts: Payouts
) -> Response:
    """Show profile details. Bank data stays in payouts-service; only the last four show."""
    destination = None
    payouts_error = False
    try:
        destination = payouts.bank_destination(user.id)
    except PayoutsUnavailable:
        payouts_error = True
    manager = session.get(User, user.manager_id) if user.manager_id else None
    return templates.TemplateResponse(
        request,
        "profile.html",
        {
            "user": user,
            "manager": manager,
            "destination": destination,
            "payouts_error": payouts_error,
        },
    )

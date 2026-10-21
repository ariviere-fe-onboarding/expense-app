"""Vacation delegation: a manager's approvals covered by another manager for a date range."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Delegation, User


def covered_managers(session: Session, user: User, today: date) -> frozenset[str]:
    """Return the IDs of managers whose approvals this user is covering today."""
    rows = session.scalars(
        select(Delegation.manager_id).where(
            Delegation.delegate_id == user.id,
            Delegation.starts_on <= today,
            Delegation.ends_on > today,
        )
    ).all()
    return frozenset(rows)


def current_delegation(session: Session, manager: User) -> Delegation | None:
    """Return the manager's delegation, if one is set."""
    return session.scalars(select(Delegation).where(Delegation.manager_id == manager.id)).first()

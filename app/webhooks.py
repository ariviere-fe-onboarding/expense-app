"""expense.approved webhooks via a transactional outbox (contract: tests/contract)."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.fx import to_usd
from app.models import Expense, User, WebhookDelivery, utcnow
from app.payouts_client import PayoutsClient, PayoutsUnavailable

logger = logging.getLogger(__name__)


def expense_approved_event(expense: Expense, approver: User) -> dict[str, object]:
    """Build the version 1 expense.approved payload."""
    return {
        "version": 1,
        "event_id": f"evt-{uuid.uuid4().hex}",
        "type": "expense.approved",
        "occurred_at": utcnow().isoformat().replace("+00:00", "Z"),
        "data": {
            "expense_id": expense.id,
            "employee_id": expense.submitter_id,
            "amount": round(to_usd(expense.amount_cents, expense.currency), 2),
            "currency": "USD",
            "approved_by": approver.id,
        },
    }


def enqueue(session: Session, expense: Expense, approver: User) -> WebhookDelivery:
    """Record the webhook in the same transaction as the approval. Caller commits."""
    payload = expense_approved_event(expense, approver)
    delivery = WebhookDelivery(
        event_id=str(payload["event_id"]), expense_id=expense.id, payload=payload
    )
    session.add(delivery)
    return delivery


def attempt(session: Session, client: PayoutsClient, delivery: WebhookDelivery) -> bool:
    """Try to deliver once, recording the outcome. Returns True when delivered."""
    delivery.attempts += 1
    try:
        client.deliver(delivery.payload)
    except PayoutsUnavailable as error:
        delivery.last_error = str(error)[:200]
        session.commit()
        logger.warning("webhook %s not delivered: %s", delivery.event_id, error)
        return False
    delivery.delivered_at = utcnow()
    delivery.last_error = None
    session.commit()
    return True


def retry_pending(session: Session, client: PayoutsClient) -> int:
    """Retry every undelivered webhook with its original event_id. Returns deliveries made."""
    pending = session.scalars(
        select(WebhookDelivery).where(WebhookDelivery.delivered_at.is_(None))
    ).all()
    return sum(attempt(session, client, delivery) for delivery in pending)

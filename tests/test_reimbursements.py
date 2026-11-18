"""Reimbursement details shown to people who can view an expense."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import FakePayouts, expense_id, login


@pytest.mark.parametrize(
    ("payout_status", "label"),
    [
        ("submitted", "Submitted"),
        ("needs_bank_account", "Needs bank account"),
        ("future_state", "Future state"),
    ],
)
def test_reimbursement_labels(
    client: TestClient, fake_payouts: FakePayouts, payout_status: str, label: str
) -> None:
    """Show the status and exact amount from Payouts Service."""
    login(client, "emp-priya")
    approved = expense_id(client, "Brightline Rail")
    fake_payouts.payouts[approved] = {
        "payout_id": 15,
        "status": payout_status,
        "amount_cents": 123_409,
        "currency": "USD",
    }

    response = client.get(f"/expenses/{approved}")

    assert response.status_code == 200
    assert f"{label} · $1,234.09" in response.text


def test_reimbursement_is_missing_after_a_404(
    client: TestClient, fake_payouts: FakePayouts
) -> None:
    """Keep the missing-payout message and skip a retry when no payout exists."""
    login(client, "emp-priya")
    approved = expense_id(client, "Brightline Rail")

    response = client.get(f"/expenses/{approved}")

    assert response.status_code == 200
    assert "Not yet sent to payouts." in response.text
    assert fake_payouts.payout_status_requests == 1


def test_reimbursement_is_hidden_on_unapproved_expense(client: TestClient) -> None:
    """Restrict reimbursement details to approved expenses."""
    login(client, "emp-priya")
    pending = expense_id(client, "Harborview Hotel")

    response = client.get(f"/expenses/{pending}")

    assert response.status_code == 200
    assert "Reimbursement" not in response.text


def test_reimbursement_detail_requires_expense_visibility(client: TestClient) -> None:
    """Deny a different employee access to the approved expense."""
    login(client, "emp-jonah")
    approved = expense_id(client, "Brightline Rail")

    assert client.get(f"/expenses/{approved}").status_code == 404


@pytest.mark.parametrize(
    ("unavailable_responses", "message"),
    [
        (1, "Submitted · $1,234.09"),
        (3, "Payout status is unavailable right now."),
    ],
)
def test_reimbursement_retries_a_503_once(
    client: TestClient, fake_payouts: FakePayouts, unavailable_responses: int, message: str
) -> None:
    """Make one retry and display its result, including another unavailable response."""
    login(client, "emp-priya")
    approved = expense_id(client, "Brightline Rail")
    fake_payouts.payouts[approved] = {
        "payout_id": 15,
        "status": "submitted",
        "amount_cents": 123_409,
        "currency": "USD",
    }
    fake_payouts.payout_status_failures = unavailable_responses

    response = client.get(f"/expenses/{approved}")

    assert response.status_code == 200
    assert message in response.text
    assert fake_payouts.payout_status_requests == 2

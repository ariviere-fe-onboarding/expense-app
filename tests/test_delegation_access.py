"""Authorization boundaries shared by both delegation demo variants."""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.config import Config
from app.models import Delegation, Expense, ExpenseStatus
from app.receipts import save_receipt
from tests.conftest import expense_id, login, sessions
from tests.test_delegation import TEST_TODAY, delegate_to_lena


@pytest.fixture(autouse=True)
def active_coverage(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Set up coverage away from the intentionally different date boundaries."""
    monkeypatch.setattr("app.routes.approvals.current_date", lambda: TEST_TODAY)
    monkeypatch.setattr("app.routes.expenses.current_date", lambda: TEST_TODAY)
    assert (
        delegate_to_lena(client, TEST_TODAY - timedelta(days=1), TEST_TODAY + timedelta(days=1))
        == 303
    )


@pytest.mark.parametrize("expense_state", list(ExpenseStatus))
def test_delegate_reads_only_submitted_expenses_and_receipts(
    client: TestClient, config: Config, expense_state: ExpenseStatus
) -> None:
    """Delegation grants pending-work access; existing access remains unchanged."""
    target = expense_id(client, "Figment Fonts")
    name, content_type = save_receipt(config.upload_dir, b"%PDF-1.7\nsynthetic receipt\n")
    with sessions(client)() as session:
        expense = session.get_one(Expense, target)
        expense.status = expense_state
        expense.receipt_file = name
        expense.receipt_content_type = content_type
        session.commit()
    login(client, "emp-lena")
    expected = 200 if expense_state is ExpenseStatus.SUBMITTED else 404
    for path in (f"/expenses/{target}", f"/expenses/{target}/receipt"):
        assert client.get(path).status_code == expected

    for user in ("emp-priya", "emp-marcus", "emp-dana"):
        login(client, user)
        assert client.get(f"/expenses/{target}").status_code == 200
        assert client.get(f"/expenses/{target}/receipt").status_code == 200


@pytest.mark.parametrize("user", ["emp-priya", "emp-dana"])
def test_non_managers_cannot_clear_delegations(client: TestClient, user: str) -> None:
    """Employee and Finance requests fail without deleting the manager's record."""
    login(client, user)
    assert client.post("/profile/delegation/clear").status_code == 403
    with sessions(client)() as session:
        assert session.query(Delegation).filter_by(manager_id="emp-marcus").count() == 1


def test_anonymous_cannot_clear_delegation(client: TestClient) -> None:
    """A direct unauthenticated clear request requires sign-in."""
    client.post("/logout")
    response = client.post("/profile/delegation/clear", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_delegate_returns_to_queue_after_decision(client: TestClient, decision: str) -> None:
    """A successful decision does not redirect to a now-inaccessible expense."""
    target = expense_id(client, "Figment Fonts")
    login(client, "emp-lena")
    response = client.post(
        f"/expenses/{target}/decision", data={"decision": decision}, follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/approvals"
    assert client.get(response.headers["location"]).status_code == 200
    assert client.get(f"/expenses/{target}").status_code == 404

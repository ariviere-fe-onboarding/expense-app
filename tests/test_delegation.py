from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import policy, webhooks
from app.models import Approval, Category, Expense, ExpenseStatus, User, WebhookDelivery
from tests.conftest import FakePayouts, expense_id, expense_status, login, sessions

TEST_TODAY = date(2026, 10, 1)


@pytest.fixture(autouse=True)
def fixed_delegation_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep approval and expense routes on the same day as the tests."""
    monkeypatch.setattr("app.routes.approvals.current_date", lambda: TEST_TODAY)
    monkeypatch.setattr("app.routes.expenses.current_date", lambda: TEST_TODAY)


def delegate_to_lena(client: TestClient, start: date, end: date) -> int:
    login(client, "emp-marcus")
    response = client.post(
        "/profile/delegation",
        data={
            "delegate_id": "emp-lena",
            "starts_on": start.isoformat(),
            "ends_on": end.isoformat(),
        },
        follow_redirects=False,
    )
    return response.status_code


def test_manager_sets_and_clears_delegation(client: TestClient) -> None:
    today = TEST_TODAY
    assert delegate_to_lena(client, today, today + timedelta(days=7)) == 303
    assert "Lena Ortiz covers your approvals" in client.get("/profile").text
    client.post("/profile/delegation/clear")
    assert "Lena Ortiz covers your approvals" not in client.get("/profile").text


def test_delegate_approves_during_vacation(client: TestClient, fake_payouts: FakePayouts) -> None:
    today = TEST_TODAY
    delegate_to_lena(client, today - timedelta(days=2), today + timedelta(days=5))
    login(client, "emp-lena")
    assert "Figment Fonts" in client.get("/approvals").text
    client.post(
        f"/expenses/{expense_id(client, 'Figment Fonts')}/decision", data={"decision": "approve"}
    )
    assert expense_status(client, "Figment Fonts") == "approved"
    assert fake_payouts.webhooks[0]["data"]["approved_by"] == "emp-lena"


def test_delegate_sends_large_expense_to_finance(client: TestClient) -> None:
    today = TEST_TODAY
    delegate_to_lena(client, today - timedelta(days=1), today + timedelta(days=1))
    login(client, "emp-lena")
    client.post(
        f"/expenses/{expense_id(client, 'Harborview Hotel')}/decision",
        data={"decision": "approve"},
    )
    assert expense_status(client, "Harborview Hotel") == "awaiting_finance"


@pytest.mark.parametrize(("start_offset", "end_offset"), [(3, 10), (-10, -3)])
def test_inactive_delegation_denies_decisions(
    client: TestClient, fake_payouts: FakePayouts, start_offset: int, end_offset: int
) -> None:
    today = TEST_TODAY
    delegate_to_lena(
        client, today + timedelta(days=start_offset), today + timedelta(days=end_offset)
    )
    login(client, "emp-lena")
    assert "Figment Fonts" not in client.get("/approvals").text
    response = client.post(
        f"/expenses/{expense_id(client, 'Figment Fonts')}/decision",
        data={"decision": "approve"},
    )
    assert response.status_code == 404
    assert expense_status(client, "Figment Fonts") == "submitted"
    assert fake_payouts.webhooks == []


def test_only_managers_can_be_delegates(client: TestClient) -> None:
    login(client, "emp-marcus")
    today = TEST_TODAY.isoformat()
    response = client.post(
        "/profile/delegation",
        data={"delegate_id": "emp-priya", "starts_on": today, "ends_on": today},
    )
    assert response.status_code == 400


def test_employees_cannot_delegate(client: TestClient) -> None:
    login(client, "emp-priya")
    today = TEST_TODAY.isoformat()
    response = client.post(
        "/profile/delegation",
        data={"delegate_id": "emp-lena", "starts_on": today, "ends_on": today},
    )
    assert response.status_code == 403


def test_end_before_start_is_rejected(client: TestClient) -> None:
    today = TEST_TODAY
    assert delegate_to_lena(client, today, today - timedelta(days=1)) == 400


@pytest.mark.parametrize(("start_offset", "end_offset"), [(0, 5), (-5, 0), (0, 0)])
@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_delegation_includes_both_endpoints(
    client: TestClient, start_offset: int, end_offset: int, decision: str
) -> None:
    """The first day, last day, and a one-day vacation all allow decisions."""
    today = TEST_TODAY
    assert (
        delegate_to_lena(
            client, today + timedelta(days=start_offset), today + timedelta(days=end_offset)
        )
        == 303
    )
    login(client, "emp-lena")
    expense = expense_id(client, "Figment Fonts")
    assert "Figment Fonts" in client.get("/approvals").text
    assert client.get(f"/expenses/{expense}").status_code == 200
    response = client.post(
        f"/expenses/{expense}/decision", data={"decision": decision}, follow_redirects=False
    )
    assert response.status_code == 303
    assert expense_status(client, "Figment Fonts") == (
        "approved" if decision == "approve" else "rejected"
    )


@pytest.mark.parametrize("amount_cents", [49_999, 50_000, 50_001])
def test_delegate_uses_inclusive_manager_limit(
    client: TestClient, fake_payouts: FakePayouts, amount_cents: int
) -> None:
    """Exactly $500 gets final approval; the first cent above still needs Finance."""
    today = TEST_TODAY
    delegate_to_lena(client, today - timedelta(days=1), today + timedelta(days=1))
    with sessions(client)() as session:
        expense = session.get(Expense, expense_id(client, "Figment Fonts"))
        assert expense is not None
        expense.amount_cents = amount_cents
        session.commit()
    login(client, "emp-lena")
    response = client.post(
        f"/expenses/{expense_id(client, 'Figment Fonts')}/decision",
        data={"decision": "approve"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    if amount_cents <= 50_000:
        assert expense_status(client, "Figment Fonts") == "approved"
        assert len(fake_payouts.webhooks) == 1
        assert fake_payouts.webhooks[0]["data"]["amount_cents"] == amount_cents
    else:
        assert expense_status(client, "Figment Fonts") == "awaiting_finance"
        assert fake_payouts.webhooks == []


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_delegate_cannot_decide_on_own_expense(
    client: TestClient, fake_payouts: FakePayouts, decision: str
) -> None:
    """Delegation never overrides the self-decision denial, even for a direct POST."""
    today = TEST_TODAY
    delegate_to_lena(client, today, today)
    with sessions(client)() as session:
        lena = session.get(User, "emp-lena")
        assert lena is not None
        lena.manager_id = "emp-marcus"
        expense = Expense(
            submitter_id=lena.id,
            merchant="Delegate's own expense",
            description="",
            category=Category.OTHER,
            amount_cents=1000,
            spent_on=today,
            status=ExpenseStatus.SUBMITTED,
        )
        session.add(expense)
        session.commit()
        own_id = expense.id
    login(client, "emp-lena")
    assert "Delegate&#39;s own expense" not in client.get("/approvals").text
    assert (
        client.post(f"/expenses/{own_id}/decision", data={"decision": decision}).status_code == 403
    )
    assert expense_status(client, "Delegate's own expense") == "submitted"
    assert fake_payouts.webhooks == []


@pytest.mark.parametrize("delegate_id", ["emp-dana", "emp-marcus", "missing-user"])
def test_invalid_delegates_are_rejected(client: TestClient, delegate_id: str) -> None:
    """Finance, self, and nonexistent accounts cannot be chosen as delegates."""
    login(client, "emp-marcus")
    today = TEST_TODAY.isoformat()
    response = client.post(
        "/profile/delegation",
        data={"delegate_id": delegate_id, "starts_on": today, "ends_on": today},
    )
    assert response.status_code == 400


def test_finance_cannot_delegate(client: TestClient) -> None:
    """The feature cannot delegate Finance's approval authority."""
    login(client, "emp-dana")
    today = TEST_TODAY.isoformat()
    assert (
        client.post(
            "/profile/delegation",
            data={"delegate_id": "emp-lena", "starts_on": today, "ends_on": today},
        ).status_code
        == 403
    )


def test_anonymous_cannot_set_delegation(client: TestClient) -> None:
    """Delegation changes require an authenticated manager."""
    today = TEST_TODAY.isoformat()
    response = client.post(
        "/profile/delegation",
        data={"delegate_id": "emp-lena", "starts_on": today, "ends_on": today},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


@pytest.mark.parametrize("winner", ["approve", "reject"])
@pytest.mark.parametrize("loser", ["approve", "reject"])
def test_competing_decision_preserves_first_committed_result(
    client: TestClient,
    fake_payouts: FakePayouts,
    monkeypatch: pytest.MonkeyPatch,
    winner: str,
    loser: str,
) -> None:
    """A stale delegate decision cannot overwrite the manager or enqueue another payout."""
    delegate_to_lena(client, TEST_TODAY - timedelta(days=1), TEST_TODAY + timedelta(days=1))
    target = expense_id(client, "Figment Fonts")
    real_can_decide = policy.can_decide

    def commit_manager_decision(
        user: User, expense: Expense, covering: frozenset[str] = frozenset()
    ) -> bool:
        allowed = real_can_decide(user, expense, covering)
        if allowed and expense.id == target:
            with sessions(client)() as other:
                current = other.get_one(Expense, target)
                manager = other.get_one(User, "emp-marcus")
                current.status = (
                    ExpenseStatus.APPROVED if winner == "approve" else ExpenseStatus.REJECTED
                )
                other.add(
                    Approval(expense_id=target, approver_id=manager.id, decision=winner, comment="")
                )
                if winner == "approve":
                    webhooks.enqueue(other, current, manager)
                other.commit()
        return allowed

    monkeypatch.setattr(policy, "can_decide", commit_manager_decision)
    login(client, "emp-lena")
    response = client.post(
        f"/expenses/{target}/decision", data={"decision": loser}, follow_redirects=False
    )
    assert response.status_code == 409
    assert expense_status(client, "Figment Fonts") == (
        "approved" if winner == "approve" else "rejected"
    )
    assert fake_payouts.webhooks == []
    with sessions(client)() as session:
        approvals = session.query(Approval).filter_by(expense_id=target).all()
        assert [(item.approver_id, item.decision) for item in approvals] == [("emp-marcus", winner)]
        deliveries = session.query(WebhookDelivery).filter_by(expense_id=target).all()
        assert len(deliveries) == (1 if winner == "approve" else 0)
        if deliveries:
            assert deliveries[0].payload["data"]["approved_by"] == "emp-marcus"

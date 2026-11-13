from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.models import Category, Expense, ExpenseStatus, User
from tests.conftest import FakePayouts, expense_id, expense_status, login, sessions


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
    today = date.today()
    assert delegate_to_lena(client, today, today + timedelta(days=7)) == 303
    assert "Lena Ortiz covers your approvals" in client.get("/profile").text
    client.post("/profile/delegation/clear")
    assert "Lena Ortiz covers your approvals" not in client.get("/profile").text


def test_delegate_approves_during_vacation(client: TestClient, fake_payouts: FakePayouts) -> None:
    today = date.today()
    delegate_to_lena(client, today - timedelta(days=2), today + timedelta(days=5))
    login(client, "emp-lena")
    assert "Figment Fonts" in client.get("/approvals").text
    client.post(
        f"/expenses/{expense_id(client, 'Figment Fonts')}/decision", data={"decision": "approve"}
    )
    assert expense_status(client, "Figment Fonts") == "approved"
    assert fake_payouts.webhooks[0]["data"]["approved_by"] == "emp-lena"


def test_delegate_sends_large_expense_to_finance(client: TestClient) -> None:
    today = date.today()
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
    today = date.today()
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
    today = date.today().isoformat()
    response = client.post(
        "/profile/delegation",
        data={"delegate_id": "emp-priya", "starts_on": today, "ends_on": today},
    )
    assert response.status_code == 400


def test_employees_cannot_delegate(client: TestClient) -> None:
    login(client, "emp-priya")
    today = date.today().isoformat()
    response = client.post(
        "/profile/delegation",
        data={"delegate_id": "emp-lena", "starts_on": today, "ends_on": today},
    )
    assert response.status_code == 403


def test_end_before_start_is_rejected(client: TestClient) -> None:
    today = date.today()
    assert delegate_to_lena(client, today, today - timedelta(days=1)) == 400


@pytest.mark.parametrize(("start_offset", "end_offset"), [(0, 5), (-5, 0), (0, 0)])
@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_delegation_includes_both_endpoints(
    client: TestClient, start_offset: int, end_offset: int, decision: str
) -> None:
    """The first day, last day, and a one-day vacation all allow decisions."""
    today = date.today()
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
    today = date.today()
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
    today = date.today()
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
    today = date.today().isoformat()
    response = client.post(
        "/profile/delegation",
        data={"delegate_id": delegate_id, "starts_on": today, "ends_on": today},
    )
    assert response.status_code == 400


def test_finance_cannot_delegate(client: TestClient) -> None:
    """The feature cannot delegate Finance's approval authority."""
    login(client, "emp-dana")
    today = date.today().isoformat()
    assert (
        client.post(
            "/profile/delegation",
            data={"delegate_id": "emp-lena", "starts_on": today, "ends_on": today},
        ).status_code
        == 403
    )


def test_anonymous_cannot_set_delegation(client: TestClient) -> None:
    """Delegation changes require an authenticated manager."""
    today = date.today().isoformat()
    response = client.post(
        "/profile/delegation",
        data={"delegate_id": "emp-lena", "starts_on": today, "ends_on": today},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/login"

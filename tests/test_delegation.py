from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient

from tests.conftest import FakePayouts, expense_id, expense_status, login


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


def test_delegation_not_active_before_it_starts(client: TestClient) -> None:
    today = date.today()
    delegate_to_lena(client, today + timedelta(days=3), today + timedelta(days=10))
    login(client, "emp-lena")
    assert "Figment Fonts" not in client.get("/approvals").text


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

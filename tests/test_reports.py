"""Finance dashboard feed response contract."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.deps import SESSION_COOKIE
from app.models import UserSession, utcnow
from tests.conftest import login, sessions


@pytest.mark.parametrize("session_state", ["missing", "invalid", "expired"])
def test_summary_requires_valid_session(client: TestClient, session_state: str) -> None:
    """Reject unauthenticated requests before querying company expense records."""
    if session_state == "invalid":
        client.cookies.set(SESSION_COOKIE, "invalid-session")
    elif session_state == "expired":
        login(client, "emp-dana")
        with sessions(client)() as session:
            for record in session.query(UserSession).all():
                record.expires_at = utcnow() - timedelta(minutes=1)
            session.commit()

    with patch(
        "app.routes.reports.select", side_effect=AssertionError("Unauthorized expense query")
    ):
        response = client.get("/reports/summary", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


@pytest.mark.parametrize("user_id", ["emp-priya", "emp-jonah", "emp-marcus", "emp-lena"])
def test_summary_denies_non_finance_users(client: TestClient, user_id: str) -> None:
    """Employees and managers cannot query the company-wide report."""
    login(client, user_id)
    with patch(
        "app.routes.reports.select", side_effect=AssertionError("Unauthorized expense query")
    ):
        response = client.get("/reports/summary", follow_redirects=False)
    assert response.status_code == 403


def test_finance_receives_expense_summary(client: TestClient) -> None:
    login(client, "emp-dana")
    response = client.get("/reports/summary")
    assert response.status_code == 200
    rows = response.json()
    assert {row["team"] for row in rows} == {"Design", "Sales"}
    assert all(isinstance(row["amount_cents"], int) for row in rows)
    assert all("password_hash" not in row for row in rows)

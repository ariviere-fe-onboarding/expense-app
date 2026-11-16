"""Finance dashboard feed response contract."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.deps import SESSION_COOKIE
from app.models import UserSession, utcnow
from tests.conftest import login, sessions


@pytest.mark.parametrize("cookie", [None, "invalid-session"])
def test_summary_requires_login(client: TestClient, cookie: str | None) -> None:
    if cookie is not None:
        client.cookies.set(SESSION_COOKIE, cookie)
    response = client.get("/reports/summary", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert not response.content


@pytest.mark.parametrize("user_id", ["emp-priya", "emp-jonah", "emp-marcus", "emp-lena"])
def test_non_finance_cannot_read_summary(client: TestClient, user_id: str) -> None:
    login(client, user_id)
    response = client.get("/reports/summary", follow_redirects=False)
    assert response.status_code == 403
    assert "Only Finance may access expense reports." in response.text
    assert "employee_email" not in response.text
    assert "Harborview Hotel" not in response.text


def test_expired_finance_session_cannot_read_summary(client: TestClient) -> None:
    login(client, "emp-dana")
    with sessions(client)() as session:
        for record in session.query(UserSession).all():
            record.expires_at = utcnow() - timedelta(minutes=1)
        session.commit()
    response = client.get("/reports/summary", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert not response.content


def test_finance_receives_expense_summary(client: TestClient) -> None:
    login(client, "emp-dana")
    response = client.get("/reports/summary")
    assert response.status_code == 200
    rows = response.json()
    assert {row["team"] for row in rows} == {"Design", "Sales"}
    assert all(isinstance(row["amount_cents"], int) for row in rows)
    assert all("password_hash" not in row for row in rows)

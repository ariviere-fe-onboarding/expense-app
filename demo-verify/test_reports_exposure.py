"""Verify the report disclosure is blocked, outside ordinary CI."""

# ruff: noqa: S101 -- these are presenter-run tests.

from fastapi.testclient import TestClient

from tests.conftest import login


def test_anonymous_visitor_cannot_read_expenses(client: TestClient) -> None:
    response = client.get("/reports/summary", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert not response.content


def test_employee_cannot_read_company_expenses(client: TestClient) -> None:
    login(client, "emp-priya")
    response = client.get("/reports/summary")
    assert response.status_code == 403
    assert "employee_email" not in response.text

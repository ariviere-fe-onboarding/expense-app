"""Verify the legacy Finance report no longer exposes expenses to unauthorized callers."""

# ruff: noqa: S101 -- these are presenter-run tests.

from fastapi.testclient import TestClient

from tests.conftest import login


def test_anonymous_visitor_cannot_read_expense_summary(client: TestClient) -> None:
    """Anonymous visitors must sign in before accessing reports."""
    response = client.get("/reports/summary", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_employee_cannot_read_expense_summary(client: TestClient) -> None:
    """Signing in as an employee does not grant access to Finance reports."""
    login(client, "emp-priya")
    response = client.get("/reports/summary", follow_redirects=False)
    assert response.status_code == 403

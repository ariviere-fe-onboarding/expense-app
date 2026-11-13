"""Characterize the deliberately vulnerable baseline, outside ordinary CI.

These tests confirm the flaw exists. They must be reversed when fixing it.
"""

# ruff: noqa: S101 -- these are presenter-run tests.

from fastapi.testclient import TestClient

from tests.conftest import login


def test_anonymous_visitor_reads_every_teams_expenses(client: TestClient) -> None:
    response = client.get("/reports/summary", follow_redirects=False)
    assert response.status_code == 200
    rows = response.json()
    assert {row["team"] for row in rows} == {"Design", "Sales"}
    assert all(row["employee_email"] for row in rows)


def test_employee_reads_another_teams_expenses(client: TestClient) -> None:
    login(client, "emp-priya")
    response = client.get("/reports/summary")
    assert response.status_code == 200
    assert any(row["team"] == "Sales" for row in response.json())

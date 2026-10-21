"""Finance dashboard feed response contract."""

from fastapi.testclient import TestClient

from tests.conftest import login


def test_finance_receives_expense_summary(client: TestClient) -> None:
    login(client, "emp-dana")
    response = client.get("/reports/summary")
    assert response.status_code == 200
    rows = response.json()
    assert {row["team"] for row in rows} == {"Design", "Sales"}
    assert all(isinstance(row["amount_cents"], int) for row in rows)
    assert all("password_hash" not in row for row in rows)

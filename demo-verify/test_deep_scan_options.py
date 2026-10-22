"""Prove the intentionally vulnerable scan options using only isolated synthetic data."""

# ruff: noqa: S101 -- presenter characterization tests assert vulnerable behavior.

from fastapi.testclient import TestClient

from app.config import Config
from app.models import Expense, ExpenseStatus
from tests.conftest import expense_id, expense_status, login, sessions


def test_employee_promotes_self_and_approves_another_teams_expense(client: TestClient) -> None:
    """A profile field grants real Finance permissions, including final approval."""
    target = expense_id(client, "Cedar & Salt")
    with sessions(client)() as session:
        expense = session.get(Expense, target)
        assert expense is not None
        expense.status = ExpenseStatus.AWAITING_FINANCE
        session.commit()
    login(client, "emp-priya")
    assert client.get("/approvals").status_code == 403
    assert client.get(f"/expenses/{target}").status_code == 404
    response = client.post("/profile", json={"name": "Priya Nair", "role": "finance"})
    assert response.status_code == 200
    assert client.get("/approvals").status_code == 200
    assert client.get(f"/expenses/{target}").status_code == 200
    decision = client.post(f"/expenses/{target}/decision", data={"decision": "approve"})
    assert decision.status_code == 200
    assert expense_status(client, "Cedar & Salt") == "approved"


def test_receipt_download_reads_synthetic_file_outside_archive(
    client: TestClient, config: Config
) -> None:
    """Traversal reads a temporary fake secret, never real host files or credentials."""
    config.upload_dir.mkdir(parents=True, exist_ok=True)
    marker = config.upload_dir.parent / "demo-private.txt"
    marker.write_text("SYNTHETIC_SECRET=receipt-demo-only\n")
    login(client, "emp-priya")
    response = client.get("/receipts/download", params={"filename": "../demo-private.txt"})
    assert response.status_code == 200
    assert response.text == marker.read_text()


def test_download_also_accepts_absolute_file_paths(client: TestClient, config: Config) -> None:
    """An absolute input replaces the archive prefix."""
    marker = config.upload_dir.parent / "demo-absolute.txt"
    marker.write_text("synthetic absolute-path marker")
    login(client, "emp-priya")
    response = client.get("/receipts/download", params={"filename": str(marker)})
    assert response.status_code == 200
    assert response.text == marker.read_text()

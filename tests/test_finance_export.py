from __future__ import annotations

import csv
import io
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.models import Category, Expense, ExpenseStatus, Role, User
from tests.conftest import expense_id, login, sessions


def _export_query_count(client: TestClient) -> int:
    """Count SELECT statements for a complete authenticated export request."""
    statements: list[str] = []

    def record_query(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: bool,
    ) -> None:
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    with sessions(client)() as session:
        engine = session.get_bind()
    event.listen(engine, "before_cursor_execute", record_query)
    try:
        export(client, "2026-09-01", "2026-09-30")
    finally:
        event.remove(engine, "before_cursor_execute", record_query)
    return len(statements)


def test_export_query_count_does_not_grow_per_submitter(client: TestClient) -> None:
    login(client, "emp-dana")
    baseline = _export_query_count(client)
    with sessions(client)() as session:
        existing = session.get(User, "emp-priya")
        assert existing is not None
        for index in range(20):
            submitter = User(
                id=f"emp-export-{index}",
                email=f"export-{index}@fernway.example",
                name=f"Export Employee {index}",
                team="Design",
                role=Role.EMPLOYEE,
                manager_id="emp-marcus",
                password_hash=existing.password_hash,
            )
            session.add(
                Expense(
                    submitter=submitter,
                    merchant=f"Export Merchant {index}",
                    description="",
                    category=Category.OTHER,
                    amount_cents=100,
                    spent_on=date(2026, 9, 15),
                    status=ExpenseStatus.APPROVED,
                )
            )
        session.commit()
    assert _export_query_count(client) <= baseline + 1


def test_anonymous_cannot_export(client: TestClient) -> None:
    response = client.get(
        "/finance/export",
        params={"start": "2026-09-01", "end": "2026-09-30"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def export(client: TestClient, start: str, end: str) -> list[list[str]]:
    response = client.get("/finance/export", params={"start": start, "end": end})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    return list(csv.reader(io.StringIO(response.text)))


def test_finance_exports_approved_expenses(client: TestClient) -> None:
    login(client, "emp-dana")
    rows = export(client, "2026-09-01", "2026-09-30")
    assert rows[0][0] == "expense_id"
    assert rows[1][1:] == [
        "2026-09-19",
        "Priya Nair",
        "Design",
        "Brightline Rail",
        "travel",
        "86.40",
    ]
    assert rows[-1] == ["total", "", "", "", "", "", "86.40"]


def test_unapproved_expenses_are_excluded(client: TestClient) -> None:
    login(client, "emp-dana")
    merchants = [row[4] for row in export(client, "2026-09-01", "2026-09-30")[1:-1]]
    assert "Figment Fonts" not in merchants


def test_formula_text_is_neutralized(client: TestClient) -> None:
    login(client, "emp-priya")
    client.post(
        "/expenses",
        data={
            "merchant": "=HYPERLINK(1)",
            "amount": "12.00",
            "spent_on": "2026-09-15",
            "category": "other",
        },
    )
    login(client, "emp-marcus")
    client.post(
        f"/expenses/{expense_id(client, '=HYPERLINK(1)')}/decision", data={"decision": "approve"}
    )
    login(client, "emp-dana")
    merchants = [row[4] for row in export(client, "2026-09-01", "2026-09-30")[1:-1]]
    assert "'=HYPERLINK(1)" in merchants


def test_only_finance_can_export(client: TestClient) -> None:
    for user in ("emp-priya", "emp-marcus"):
        login(client, user)
        response = client.get(
            "/finance/export", params={"start": "2026-09-01", "end": "2026-09-30"}
        )
        assert response.status_code == 403


def test_reversed_range_is_rejected(client: TestClient) -> None:
    login(client, "emp-dana")
    response = client.get("/finance/export", params={"start": "2026-09-30", "end": "2026-09-01"})
    assert response.status_code == 400


@pytest.mark.parametrize(
    ("start", "end"),
    [("2026-09-19", "2026-09-19"), ("2026-09-01", "2026-09-19"), ("2026-09-19", "2026-09-30")],
)
def test_export_includes_both_date_endpoints(client: TestClient, start: str, end: str) -> None:
    """A one-day range and each endpoint include the approved expense."""
    login(client, "emp-dana")
    rows = export(client, start, end)
    assert [row[4] for row in rows[1:-1]] == ["Brightline Rail"]
    assert rows[-1][-1] == "86.40"


def test_export_excludes_dates_outside_range(client: TestClient) -> None:
    """Out-of-range expenses do not contribute to an empty export's total."""
    login(client, "emp-dana")
    for start, end in [("2026-09-01", "2026-09-18"), ("2026-09-20", "2026-09-30")]:
        rows = export(client, start, end)
        assert len(rows) == 2
        assert rows[-1][-1] == "0.00"


def test_full_month_export_totals_exact_cents(client: TestClient) -> None:
    """A 2,000-row month retains every cent and avoids per-row database queries."""
    login(client, "emp-dana")
    baseline = _export_query_count(client)
    amounts_cents = [1, 10, 29, 99, 999_999] * 400
    with sessions(client)() as session:
        session.add_all(
            Expense(
                submitter_id="emp-priya",
                merchant=f"Month-end expense {index}",
                description="",
                category=Category.OTHER,
                amount_cents=amount_cents,
                spent_on=date(2026, 9, 30),
                status=ExpenseStatus.APPROVED,
            )
            for index, amount_cents in enumerate(amounts_cents)
        )
        session.commit()
    rows = export(client, "2026-09-30", "2026-09-30")
    assert len(rows) == 2002
    assert [Decimal(row[-1]) * 100 for row in rows[1:-1]] == amounts_cents
    assert Decimal(rows[-1][-1]) * 100 == sum(amounts_cents)
    assert sum(Decimal(row[-1]) for row in rows[1:-1]) == Decimal(rows[-1][-1])
    assert _export_query_count(client) <= baseline + 1


def test_export_form_is_shown_only_to_finance(client: TestClient) -> None:
    """Finance can select a date range from Approvals; managers cannot export."""
    login(client, "emp-dana")
    assert 'action="/finance/export"' in client.get("/approvals").text
    login(client, "emp-marcus")
    assert 'action="/finance/export"' not in client.get("/approvals").text


@pytest.mark.parametrize("start", ["not-a-date", "2026-02-30"])
def test_invalid_export_dates_are_rejected(client: TestClient, start: str) -> None:
    """Malformed external date input fails boundary validation."""
    login(client, "emp-dana")
    assert (
        client.get("/finance/export", params={"start": start, "end": "2026-09-30"}).status_code
        == 422
    )

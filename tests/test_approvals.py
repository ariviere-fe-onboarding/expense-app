from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.models import WebhookDelivery
from app.payouts_client import PayoutsClient
from app.webhooks import retry_pending
from tests.conftest import CONTRACT_FIXTURE, FakePayouts, expense_id, expense_status, login


def decide(client: TestClient, merchant: str, decision: str = "approve") -> int:
    response = client.post(
        f"/expenses/{expense_id(client, merchant)}/decision",
        data={"decision": decision, "comment": "ok"},
        follow_redirects=False,
    )
    return response.status_code


def test_manager_approves_small_expense_as_final(
    client: TestClient, fake_payouts: FakePayouts
) -> None:
    login(client, "emp-marcus")
    assert decide(client, "Figment Fonts") == 303
    assert expense_status(client, "Figment Fonts") == "approved"
    assert len(fake_payouts.webhooks) == 1


def test_limit_is_inclusive_at_500(client: TestClient, fake_payouts: FakePayouts) -> None:
    login(client, "emp-priya")
    client.post(
        "/expenses",
        data={
            "merchant": "Exact Limit",
            "amount": "500.00",
            "spent_on": "2026-09-30",
            "category": "other",
        },
    )
    login(client, "emp-marcus")
    decide(client, "Exact Limit")
    assert expense_status(client, "Exact Limit") == "approved"


def test_large_expense_needs_finance(client: TestClient, fake_payouts: FakePayouts) -> None:
    login(client, "emp-marcus")
    decide(client, "Harborview Hotel")
    assert expense_status(client, "Harborview Hotel") == "awaiting_finance"
    assert fake_payouts.webhooks == []
    login(client, "emp-dana")
    assert decide(client, "Harborview Hotel") == 303
    assert expense_status(client, "Harborview Hotel") == "approved"
    assert fake_payouts.webhooks[0]["data"]["approved_by"] == "emp-dana"


def test_manager_cannot_approve_other_team(client: TestClient) -> None:
    login(client, "emp-lena")
    assert decide(client, "Figment Fonts") == 404
    assert expense_status(client, "Figment Fonts") == "submitted"


def test_employee_cannot_approve(client: TestClient) -> None:
    login(client, "emp-jonah")
    assert decide(client, "Cedar & Salt") == 403
    assert expense_status(client, "Cedar & Salt") == "submitted"


def test_finance_cannot_skip_manager(client: TestClient) -> None:
    login(client, "emp-dana")
    assert decide(client, "Figment Fonts") == 403


def test_nobody_approves_their_own_expense(client: TestClient) -> None:
    login(client, "emp-dana")
    client.post(
        "/expenses",
        data={
            "merchant": "Dana Taxi",
            "amount": "30.00",
            "spent_on": "2026-09-30",
            "category": "travel",
        },
    )
    assert expense_status(client, "Dana Taxi") == "awaiting_finance"
    assert decide(client, "Dana Taxi") == 403
    assert "Dana Taxi" not in client.get("/approvals").text


def test_decided_expense_cannot_be_decided_again(
    client: TestClient, fake_payouts: FakePayouts
) -> None:
    login(client, "emp-marcus")
    decide(client, "Figment Fonts")
    assert decide(client, "Figment Fonts") == 403
    assert len(fake_payouts.webhooks) == 1


def test_reject(client: TestClient, fake_payouts: FakePayouts) -> None:
    login(client, "emp-lena")
    assert decide(client, "Cedar & Salt", "reject") == 303
    assert expense_status(client, "Cedar & Salt") == "rejected"
    assert fake_payouts.webhooks == []


def test_queues_show_the_right_work(client: TestClient) -> None:
    login(client, "emp-marcus")
    marcus = client.get("/approvals").text
    assert "Figment Fonts" in marcus
    assert "Cedar &amp; Salt" not in marcus
    login(client, "emp-dana")
    dana = client.get("/approvals").text
    assert "Monitor Depot" in dana
    assert "Figment Fonts" not in dana
    login(client, "emp-priya")
    assert client.get("/approvals").status_code == 403


def test_webhook_matches_pinned_contract(client: TestClient, fake_payouts: FakePayouts) -> None:
    login(client, "emp-lena")
    decide(client, "Cedar & Salt")
    sent = fake_payouts.webhooks[0]
    pinned = json.loads(CONTRACT_FIXTURE.read_text(encoding="utf-8"))
    assert sent.keys() == pinned.keys()
    assert sent["data"].keys() == pinned["data"].keys()
    for key in ("version", "type"):
        assert sent[key] == pinned[key]
    for key, value in pinned["data"].items():
        assert type(sent["data"][key]) is type(value), key
    assert sent["data"]["amount_cents"] == 18_450
    assert sent["data"]["employee_id"] == "emp-jonah"


def test_payout_status_shown_after_approval(client: TestClient) -> None:
    login(client, "emp-lena")
    decide(client, "Cedar & Salt")
    page = client.get(f"/expenses/{expense_id(client, 'Cedar & Salt')}").text
    assert "Submitted · $184.50" in page


def test_payouts_outage_keeps_approval_and_retries(
    client: TestClient, fake_payouts: FakePayouts
) -> None:
    fake_payouts.fail = True
    login(client, "emp-lena")
    assert decide(client, "Cedar & Salt") == 303
    assert expense_status(client, "Cedar & Salt") == "approved"
    page = client.get(f"/expenses/{expense_id(client, 'Cedar & Salt')}").text
    assert "Payout status is unavailable" in page

    fake_payouts.fail = False
    app = client.app
    with app.state.session_factory() as session:
        original = session.query(WebhookDelivery).one().event_id
        assert (
            retry_pending(session, PayoutsClient(app.state.config, app.state.payouts.transport))
            == 1
        )
        assert (
            retry_pending(session, PayoutsClient(app.state.config, app.state.payouts.transport))
            == 0
        )
    assert fake_payouts.webhooks[0]["event_id"] == original

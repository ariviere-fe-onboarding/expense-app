from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.categorizer import MODEL, Categorizer
from app.models import Category, Expense
from tests.conftest import app_of, login, sessions


class FakeMessages:
    """Records requests and replies with a fixed text block."""

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.requests: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.requests.append(kwargs)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self.reply)])


def fake_categorizer(reply: str) -> tuple[Categorizer, FakeMessages]:
    messages = FakeMessages(reply)
    client = SimpleNamespace(beta=SimpleNamespace(messages=messages))
    return Categorizer("test-key", client=client), messages  # type: ignore[arg-type]


def submit(client: TestClient, category: str) -> int:
    response = client.post(
        "/expenses",
        data={
            "merchant": "Blue Bottle",
            "amount": "6.50",
            "spent_on": "2026-09-30",
            "category": category,
            "description": "Coffee before the client workshop",
        },
        follow_redirects=False,
    )
    return response.status_code


def test_suggests_category(client: TestClient) -> None:
    categorizer, messages = fake_categorizer("meals")
    app_of(client).state.categorizer = categorizer
    login(client, "emp-priya")
    assert "Suggest for me" in client.get("/expenses/new").text
    assert submit(client, "auto") == 303
    with sessions(client)() as session:
        expense = session.query(Expense).filter_by(merchant="Blue Bottle").one()
        assert expense.category is Category.MEALS
    request = messages.requests[0]
    assert request["model"] == MODEL
    assert "<merchant>Blue Bottle</merchant>" in request["messages"][0]["content"]


def test_chosen_category_skips_suggestion(client: TestClient) -> None:
    categorizer, messages = fake_categorizer("meals")
    app_of(client).state.categorizer = categorizer
    login(client, "emp-priya")
    assert submit(client, "travel") == 303
    assert messages.requests == []


def test_feature_off_without_key(client: TestClient) -> None:
    login(client, "emp-priya")
    assert "Suggest for me" not in client.get("/expenses/new").text
    assert submit(client, "auto") == 400


@pytest.mark.parametrize("reply", ["Travel", " software\n"])
def test_reply_is_normalized(reply: str) -> None:
    categorizer, _ = fake_categorizer(reply)
    assert categorizer.suggest("Lyft", "Ride to the airport") in (
        Category.TRAVEL,
        Category.SOFTWARE,
    )

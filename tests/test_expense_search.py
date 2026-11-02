"""Employee expense-history search behavior."""

from fastapi.testclient import TestClient

from tests.conftest import login


def test_search_matches_merchant(client: TestClient) -> None:
    """A merchant fragment finds the matching expense."""
    login(client, "emp-priya")
    response = client.get("/", params={"q": "Harborview"})
    assert response.status_code == 200
    assert "Harborview Hotel" in response.text
    assert "Figment Fonts" not in response.text


def test_search_matches_description(client: TestClient) -> None:
    """A description fragment finds the matching expense."""
    login(client, "emp-priya")
    response = client.get("/", params={"q": "typeface"})
    assert "Figment Fonts" in response.text
    assert "Harborview Hotel" not in response.text


def test_plain_search_does_not_show_another_employees_expenses(client: TestClient) -> None:
    """An ordinary search stays within the employee's expense history."""
    login(client, "emp-priya")
    response = client.get("/", params={"q": "Cedar"})
    assert "No expenses match your search" in response.text
    assert "Cedar &amp; Salt" not in response.text


def test_search_requires_login(client: TestClient) -> None:
    """The new query path retains the login requirement."""
    response = client.get("/", params={"q": "hotel"}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_empty_search_shows_own_history(client: TestClient) -> None:
    """Clearing search restores the ordinary expense list."""
    login(client, "emp-priya")
    response = client.get("/", params={"q": ""})
    assert "Harborview Hotel" in response.text
    assert "Figment Fonts" in response.text
    assert "Cedar &amp; Salt" not in response.text

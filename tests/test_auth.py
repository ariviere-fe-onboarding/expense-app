from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient

from app.models import UserSession, utcnow
from app.security import hash_password, verify_password
from tests.conftest import DEMO_PASSWORD, login, sessions


def test_pages_require_login(client: TestClient) -> None:
    for path in ("/", "/expenses/new", "/approvals", "/profile", "/expenses/1"):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/login"


def test_login_and_logout(client: TestClient) -> None:
    login(client, "emp-priya")
    assert "Priya Nair" in client.get("/").text
    client.post("/logout")
    assert client.get("/", follow_redirects=False).status_code == 303


def test_wrong_password_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/login", data={"email": "priya@fernway.example", "password": "wrong-password"}
    )
    assert response.status_code == 401
    assert "incorrect" in response.text


def test_unknown_email_gets_same_error(client: TestClient) -> None:
    response = client.post("/login", data={"email": "nobody@fernway.example", "password": "x"})
    assert response.status_code == 401
    assert "incorrect" in response.text


def test_session_cookie_is_httponly(client: TestClient) -> None:
    response = client.post(
        "/login",
        data={"email": "priya@fernway.example", "password": DEMO_PASSWORD},
        follow_redirects=False,
    )
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie


def test_expired_session_is_rejected(client: TestClient) -> None:
    login(client, "emp-priya")
    with sessions(client)() as session:
        for record in session.query(UserSession).all():
            record.expires_at = utcnow() - timedelta(minutes=1)
        session.commit()
    assert client.get("/", follow_redirects=False).status_code == 303


def test_session_token_is_hashed_at_rest(client: TestClient) -> None:
    login(client, "emp-priya")
    cookie = client.cookies.get("fernway_session")
    with sessions(client)() as session:
        stored = [record.token_hash for record in session.query(UserSession).all()]
    assert cookie not in stored
    assert len(stored) == 1


def test_password_hash_round_trip() -> None:
    stored = hash_password("a long passphrase")
    assert verify_password("a long passphrase", stored)
    assert not verify_password("a different one", stored)
    assert not verify_password("anything", "md5$abc")

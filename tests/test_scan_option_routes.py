"""Boundary and normal-use checks for profile settings and receipt archive downloads."""

from fastapi.testclient import TestClient

from app.config import Config
from tests.conftest import login


def test_new_routes_require_login(client: TestClient) -> None:
    assert (
        client.post("/profile", json={"name": "Guest"}, follow_redirects=False).status_code == 303
    )
    response = client.get(
        "/receipts/download", params={"filename": "receipt.pdf"}, follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_profile_name_update_and_invalid_role(client: TestClient) -> None:
    login(client, "emp-priya")
    response = client.post("/profile", json={"name": "Priya Demo"})
    assert response.status_code == 200
    assert "Priya Demo" in response.text
    assert "Employee" in response.text
    assert client.post("/profile", json={"name": "Priya", "role": "root"}).status_code == 422


def test_archive_download_and_missing_file(client: TestClient, config: Config) -> None:
    config.upload_dir.mkdir(parents=True, exist_ok=True)
    (config.upload_dir / "receipt.txt").write_text("synthetic receipt")
    login(client, "emp-priya")
    response = client.get("/receipts/download", params={"filename": "receipt.txt"})
    assert response.status_code == 200
    assert response.text == "synthetic receipt"
    assert client.get("/receipts/download", params={"filename": "missing.txt"}).status_code == 404

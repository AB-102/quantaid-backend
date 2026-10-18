"""The public file route and the health check."""

from bson import ObjectId


def test_invalid_file_id(client):
    assert client.get("/api/files/not-an-id").status_code == 404


def test_missing_file(client):
    assert client.get(f"/api/files/{ObjectId()}").status_code == 404


def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "database": "connected"}

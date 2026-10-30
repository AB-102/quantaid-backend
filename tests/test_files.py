"""The public file route and the health check."""

from bson import ObjectId
from gridfs import GridFS


def test_allowed_image_is_shown_inline(client, test_db):
    file_id = GridFS(test_db).put(b"png-bytes", filename="_test_inline.png", content_type="image/png")
    res = client.get(f"/api/files/{file_id}")
    assert res.headers["content-type"] == "image/png"
    assert res.headers["content-disposition"].startswith("inline")
    assert res.headers["x-content-type-options"] == "nosniff"


def test_other_stored_types_are_downloads(client, test_db):
    # Only files stored before uploads were restricted can have a type like this
    file_id = GridFS(test_db).put(b"<script>alert(1)</script>", filename="_test_legacy.html", content_type="text/html")
    res = client.get(f"/api/files/{file_id}")
    assert res.headers["content-type"] == "application/octet-stream"
    assert res.headers["content-disposition"].startswith("attachment")
    assert res.headers["x-content-type-options"] == "nosniff"


def test_invalid_file_id(client):
    assert client.get("/api/files/not-an-id").status_code == 404


def test_missing_file(client):
    assert client.get(f"/api/files/{ObjectId()}").status_code == 404


def test_health(client):
    # /api/health is the same check, reachable through the site's proxy
    expected = {"status": "ok", "database": "connected", "commit": None, "version": None}
    assert client.get("/health").json() == expected
    assert client.get("/api/health").json() == expected

"""Recognising our own file URLs (so uploads are never mistaken for Google picture URLs)."""

from core.file_urls import file_url, uploaded_file_id

FILE_ID = "0123456789abcdef01234567"


def test_file_url():
    assert file_url(FILE_ID) == f"/api/files/{FILE_ID}"


def test_current_and_older_upload_urls_are_recognised():
    assert uploaded_file_id(f"/api/files/{FILE_ID}") == FILE_ID
    assert uploaded_file_id(f"/file/{FILE_ID}") == FILE_ID
    assert uploaded_file_id(f"/api/file/{FILE_ID}") == FILE_ID


def test_other_urls_are_not_uploads():
    assert uploaded_file_id("https://lh3.googleusercontent.com/a/photo.jpg") is None
    assert uploaded_file_id(f"https://example.com/api/files/{FILE_ID}") is None
    assert uploaded_file_id("/api/files/not-an-id") is None
    assert uploaded_file_id("") is None
    assert uploaded_file_id(None) is None

"""URLs for files stored in GridFS and served by GET /api/files/{id}."""

import re

# Uploads made before the FastAPI migration were stored as /file/<id>; scripts/rewrite_picture_urls.py
# rewrites them, but until it has run on a database both forms can appear.
_UPLOADED_FILE_URL = re.compile(r"^(?:/api/files|/api/file|/file)/([0-9a-f]{24})$")


def file_url(file_id: object) -> str:
    return f"/api/files/{file_id}"


def uploaded_file_id(url: str | None) -> str | None:
    """The GridFS id in one of our file URLs, or None for anything else (such as a Google picture URL)."""
    match = _UPLOADED_FILE_URL.match(url or "")
    return match.group(1) if match else None

"""
Shared test fixtures.

Tests run the real app against a dedicated test database (MONGODB_URI_TEST). Everything a test
creates uses the "_test_" prefix (or a courseId >= 9000 for lessons) and is removed after each test.
"""

import os
import secrets

import httpx
import pytest
from dotenv import load_dotenv
from gridfs import GridFS
from pymongo import MongoClient
from pymongo.errors import ConfigurationError

load_dotenv()

_test_uri = os.getenv("MONGODB_URI_TEST", "")
if not _test_uri.strip():
    raise RuntimeError("MONGODB_URI_TEST is not set. Tests need a dedicated test database.")
_sync_client = MongoClient(_test_uri, tz_aware=True)
try:
    _sync_db = _sync_client.get_default_database()
except ConfigurationError:
    # Without a database name the app would fall back to the production database name
    raise RuntimeError("MONGODB_URI_TEST must name a database, e.g. mongodb+srv://.../quantaid-test") from None

TEST_GOOGLE_CLIENT_ID = "test-google-client-id"

# Point the app at the test database, and fix its sign-in settings, before it is imported
os.environ["MONGODB_URI"] = _test_uri
os.environ["IS_RICE_DEPLOYMENT"] = "false"
os.environ["GOOGLE_CLIENT_ID"] = TEST_GOOGLE_CLIENT_ID

from fastapi.testclient import TestClient  # noqa: E402

from core.jwt import create_access_token  # noqa: E402
from main import app  # noqa: E402
from services.google_auth_service import GOOGLE_TOKENINFO_URL  # noqa: E402

TEST_PREFIX = "_test_"
TEST_COURSE_ID_START = 9000


@pytest.fixture(scope="session")
def client():
    # One TestClient for the whole run means one event loop. The app's async Mongo client
    # binds to the first loop that uses it, so tests use the sync `test_db` for their own queries.
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def test_db():
    return _sync_db


@pytest.fixture(autouse=True)
def cleanup(client):
    yield
    client.cookies.clear()
    _sync_db.users.delete_many({"user_id": {"$regex": f"^{TEST_PREFIX}"}})
    _sync_db.feedback.delete_many({"category": {"$regex": f"^{TEST_PREFIX}"}})
    _sync_db.lessons_v2.delete_many({"courseId": {"$gte": TEST_COURSE_ID_START}})
    _sync_db.lesson_revisions.delete_many({"courseId": {"$gte": TEST_COURSE_ID_START}})
    fs = GridFS(_sync_db)
    for file_doc in _sync_db["fs.files"].find({"filename": {"$regex": f"^{TEST_PREFIX}"}}, {"_id": 1}):
        fs.delete(file_doc["_id"])


@pytest.fixture
def login_as(client):
    """Create a test user and sign the client in as them. Returns the user's email."""

    def _login_as(local_part: str, is_admin: bool = False, **fields) -> str:
        email = f"{TEST_PREFIX}{local_part}@test.com"
        login_id = secrets.token_hex(32)
        _sync_db.users.insert_one(
            {
                "user_id": email,
                "login_id": login_id,
                "is_admin": is_admin,
                "completedQuizzes": [],
                **fields,
            }
        )
        client.cookies.set("quantaid_token", create_access_token(email, login_id))
        return email

    return _login_as


@pytest.fixture
def google_userinfo(monkeypatch):
    """
    Make Google answer for the access token with the given identity (or status code): tokeninfo says the token
    was issued to `aud`, our client by default, and userinfo returns the identity.
    """

    def _set(
        email: str = "",
        sub: str = "",
        name: str = "Google User",
        picture: str = "",
        status_code: int = 200,
        aud: str = TEST_GOOGLE_CLIENT_ID,
    ):
        async def fake_get(_self, url, **_kwargs):
            if url == GOOGLE_TOKENINFO_URL:
                body = {"aud": aud, "sub": sub, "email": email}
            else:
                body = {"email": email, "sub": sub, "name": name, "picture": picture}
            return httpx.Response(status_code, json=body, request=httpx.Request("GET", url))

        monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    return _set

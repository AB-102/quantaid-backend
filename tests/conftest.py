"""
Shared test fixtures.

Tests run the real app against a dedicated test database (MONGODB_URI_TEST). Everything a test
creates uses the "_test_" prefix (or a courseId >= 9000 for lessons) and is removed after each test.
"""

import json
import os
import secrets
import time

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from dotenv import load_dotenv
from gridfs import GridFS
from jwt.algorithms import RSAAlgorithm
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
TEST_RICE_CLIENT_ID = "test-rice-client-id"
# Has characters that client_secret_basic must form-encode
TEST_RICE_CLIENT_SECRET = "test rice:secret/+"
TEST_RICE_REDIRECT_URI = "http://testserver/api/auth/rice/callback"
TEST_FRONTEND_URL = "http://frontend.test"

# Point the app at the test database, and fix its sign-in settings, before it is imported
os.environ["MONGODB_URI"] = _test_uri
os.environ["IS_RICE_DEPLOYMENT"] = "false"
os.environ["GOOGLE_CLIENT_ID"] = TEST_GOOGLE_CLIENT_ID
# The Rice settings too, so tests can switch on Rice sign-in with monkeypatch.setattr("routers.auth.IS_RICE_DEPLOYMENT")
os.environ["RICE_OIDC_CLIENT_ID"] = TEST_RICE_CLIENT_ID
os.environ["RICE_OIDC_CLIENT_SECRET"] = TEST_RICE_CLIENT_SECRET
os.environ["RICE_OIDC_REDIRECT_URI"] = TEST_RICE_REDIRECT_URI
os.environ["FRONTEND_URL"] = TEST_FRONTEND_URL
# Turn email off, so a Resend key in a local .env never sends real mail from tests
os.environ["RESEND_API_KEY"] = ""

from fastapi.testclient import TestClient  # noqa: E402

from core.jwt import create_access_token  # noqa: E402
from main import app  # noqa: E402
from services.google_auth_service import GOOGLE_TOKENINFO_URL  # noqa: E402
from services.rice_auth_service import RICE_ISSUER, RICE_JWKS_URL, RICE_TOKEN_URL, RICE_USERINFO_URL  # noqa: E402

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


# The fake Rice IdP's signing key, published under the key ID Rice uses, and a key Rice never published
RICE_SIGNING_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
UNPUBLISHED_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_RICE_KID = "defaultRSASign"


def _rice_jwks() -> dict:
    public_jwk = json.loads(RSAAlgorithm.to_jwk(RICE_SIGNING_KEY.public_key()))
    return {"keys": [{**public_jwk, "kid": _RICE_KID, "use": "sig", "alg": "RS256"}]}


@pytest.fixture
def rice_idp(monkeypatch):
    """
    Make Rice's IdP answer the callback's token, key set and userinfo requests for the given user. The ID token
    is signed with RICE_SIGNING_KEY under Rice's key ID. A test can break one step:
    - `claims`: merged into the ID token's claims; a value of None leaves that claim out
    - `signing_key` / `algorithm`: sign the ID token differently
    - `token_status`: the token endpoint's status code
    - `userinfo`: merged into the userinfo response
    Returns a dict that records the token and userinfo requests.
    """

    def _set(
        *,
        email: str,
        sub: str,
        nonce: str,
        name: str | None = "Rice User",
        claims: dict | None = None,
        signing_key: rsa.RSAPrivateKey | str = RICE_SIGNING_KEY,
        algorithm: str = "RS256",
        token_status: int = 200,
        userinfo: dict | None = None,
    ) -> dict:
        now = int(time.time())
        id_claims = {
            "iss": RICE_ISSUER,
            "aud": TEST_RICE_CLIENT_ID,
            "sub": sub,
            "nonce": nonce,
            "iat": now,
            "exp": now + 300,
        }
        id_claims = {key: value for key, value in {**id_claims, **(claims or {})}.items() if value is not None}
        id_token = jwt.encode(id_claims, signing_key, algorithm=algorithm, headers={"kid": _RICE_KID})
        userinfo_body = {"sub": sub, "email": email, "name": name, **(userinfo or {})}
        requests: dict = {}

        async def fake_post(_self, url, **kwargs):
            assert url == RICE_TOKEN_URL
            requests["token"] = kwargs
            body = {"access_token": "rice-access-token", "token_type": "Bearer", "id_token": id_token}
            if token_status != 200:
                body = {"error": "invalid_grant", "error_description": "<script>alert(1)</script>"}
            return httpx.Response(token_status, json=body, request=httpx.Request("POST", url))

        async def fake_get(_self, url, **kwargs):
            if url == RICE_JWKS_URL:
                body = _rice_jwks()
            elif url == RICE_USERINFO_URL:
                requests["userinfo"] = kwargs
                body = userinfo_body
            else:
                raise AssertionError(f"unexpected GET {url}")
            return httpx.Response(200, json=body, request=httpx.Request("GET", url))

        monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
        monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
        return requests

    return _set

"""
Shared test fixtures.

Uses a dedicated MongoDB test database via MONGODB_URI_TEST to isolate tests
from dev/production data. A dedicated test prefix is used for user emails as
an extra safeguard.
"""

import os
import sys

import pytest

# Ensure the project root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ---------------------------------------------------------------------------
# Override database.mongo.db with a test-only connection BEFORE the Flask app
# (and any route/service modules) are imported.  This ensures every module that
# does ``from database.mongo import db`` gets the test database.
# ---------------------------------------------------------------------------
from dotenv import load_dotenv

load_dotenv()

_test_uri = os.getenv("MONGODB_URI_TEST", "")
if not _test_uri.strip():
    raise RuntimeError(
        "MONGODB_URI_TEST is not set. Tests require a dedicated test MongoDB URI. "
        "Set MONGODB_URI_TEST in your .env file."
    )

from pymongo.errors import ConfigurationError  # noqa: E402
from pymongo.mongo_client import MongoClient  # noqa: E402

_test_client = MongoClient(_test_uri)
try:
    _test_db = _test_client.get_default_database()
except ConfigurationError:
    _test_db = _test_client.get_database("quantaied_test")

# Importing database.mongo triggers the production client to be created,
# but we immediately replace db with our test database.
import database.mongo  # noqa: E402

database.mongo.db = _test_db


TEST_USER_PREFIX = "_test_"


@pytest.fixture(scope="session")
def app():
    """Create a Flask test app with all blueprints registered."""
    from app import app as flask_app
    from app import limiter

    flask_app.config["TESTING"] = True
    flask_app.config["SESSION_COOKIE_SECURE"] = False  # Allow non-HTTPS in tests
    flask_app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    # Disable rate limiting in tests
    limiter.enabled = False
    yield flask_app


@pytest.fixture()
def client(app):
    """Flask test client with session/cookie support."""
    with app.test_client() as c:
        yield c


@pytest.fixture(autouse=True)
def cleanup_test_users():
    """Remove any test users created during the test."""
    yield
    database.mongo.db.users.delete_many({"user_id": {"$regex": f"^{TEST_USER_PREFIX}"}})

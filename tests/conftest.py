"""
Shared test fixtures.

Uses a dedicated MongoDB Atlas *test* database for integration tests. The database
name must include 'test' to avoid accidentally running against dev or production
data. A dedicated test prefix is also used for user emails as an extra safeguard.
"""
import pytest
import sys
import os

# Ensure the project root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


TEST_USER_PREFIX = '_test_'


@pytest.fixture(scope='session')
def app():
    """Create a Flask test app with all blueprints registered."""
    from app import app as flask_app, limiter
    flask_app.config['TESTING'] = True
    flask_app.config['SESSION_COOKIE_SECURE'] = False  # Allow non-HTTPS in tests
    flask_app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
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
    from database.mongo import db
    db_name = str(getattr(db, "name", "")).lower()
    if "test" not in db_name:
        raise RuntimeError(
            f"Refusing to run cleanup_test_users against non-test database '{db_name}'. "
            "Ensure your MONGODB_URI points at a test database whose name includes 'test'."
        )
    db.users.delete_many({'user_id': {'$regex': f'^{TEST_USER_PREFIX}'}})

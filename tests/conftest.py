"""
Shared test fixtures.

Uses the real MongoDB Atlas database (same as dev) — these are integration tests.
A dedicated test prefix is used for user emails to avoid polluting real data.
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
    db.users.delete_many({'user_id': {'$regex': f'^{TEST_USER_PREFIX}'}})

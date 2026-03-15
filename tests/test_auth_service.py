"""Unit tests for services/auth_service.py."""
import pytest
from tests.conftest import TEST_USER_PREFIX
from services.auth_service import (
    hash_password,
    verify_password,
    generate_login_id,
    get_user_by_email,
    create_email_user,
    authenticate_user,
    rotate_login_id,
    create_password_reset_token,
    reset_password_with_token,
)


class TestPasswordHashing:
    def test_hash_and_verify(self):
        pw = 'testpassword123'
        hashed = hash_password(pw)
        assert hashed != pw
        assert verify_password(pw, hashed)

    def test_wrong_password_fails(self):
        hashed = hash_password('correct')
        assert not verify_password('wrong', hashed)

    def test_verify_garbage_hash_returns_false(self):
        assert not verify_password('anything', 'not_a_real_hash')

    def test_hashes_are_unique(self):
        h1 = hash_password('same')
        h2 = hash_password('same')
        assert h1 != h2  # Argon2 uses random salt


class TestGenerateLoginId:
    def test_returns_hex_string(self):
        lid = generate_login_id()
        assert isinstance(lid, str)
        assert len(lid) == 64  # 32 bytes → 64 hex chars
        int(lid, 16)  # Should not raise

    def test_unique(self):
        ids = {generate_login_id() for _ in range(20)}
        assert len(ids) == 20


class TestCreateEmailUser:
    def test_creates_user(self, app):
        with app.app_context():
            email = f'{TEST_USER_PREFIX}create@test.com'
            user = create_email_user(email, 'password123', 'Test User')
            assert user.email == email
            assert user.has_password
            assert not user.has_google
            assert user.name == 'Test User'
            assert user.login_id

    def test_lookup_after_create(self, app):
        with app.app_context():
            email = f'{TEST_USER_PREFIX}lookup@test.com'
            create_email_user(email, 'password123')
            found = get_user_by_email(email)
            assert found is not None
            assert found.email == email


class TestAuthenticateUser:
    def test_correct_credentials(self, app):
        with app.app_context():
            email = f'{TEST_USER_PREFIX}auth@test.com'
            create_email_user(email, 'mypassword8')
            user, error = authenticate_user(email, 'mypassword8')
            assert user is not None
            assert error == ''

    def test_wrong_password(self, app):
        with app.app_context():
            email = f'{TEST_USER_PREFIX}authwrong@test.com'
            create_email_user(email, 'mypassword8')
            user, error = authenticate_user(email, 'wrongpass8')
            assert user is None
            assert 'Invalid' in error

    def test_nonexistent_email(self, app):
        with app.app_context():
            user, error = authenticate_user(f'{TEST_USER_PREFIX}ghost@test.com', 'any')
            assert user is None
            assert 'Invalid' in error

    def test_lockout_after_max_attempts(self, app):
        with app.app_context():
            email = f'{TEST_USER_PREFIX}lockout@test.com'
            create_email_user(email, 'mypassword8')
            for _ in range(5):
                authenticate_user(email, 'wrongpass8')
            user, error = authenticate_user(email, 'mypassword8')
            assert user is None
            assert 'locked' in error.lower()


class TestRotateLoginId:
    def test_changes_login_id(self, app):
        with app.app_context():
            email = f'{TEST_USER_PREFIX}rotate@test.com'
            user = create_email_user(email, 'password123')
            old_id = user.login_id
            new_id = rotate_login_id(email)
            assert new_id != old_id
            refreshed = get_user_by_email(email)
            assert refreshed.login_id == new_id


class TestPasswordReset:
    def test_create_and_use_token(self, app):
        with app.app_context():
            email = f'{TEST_USER_PREFIX}reset@test.com'
            create_email_user(email, 'oldpassword1')
            token = create_password_reset_token(email)
            assert token is not None

            success, error = reset_password_with_token(token, 'newpassword1')
            assert success
            assert error == ''

            # Old password no longer works
            user, _ = authenticate_user(email, 'oldpassword1')
            assert user is None
            # New password works
            user, _ = authenticate_user(email, 'newpassword1')
            assert user is not None

    def test_invalid_token(self, app):
        with app.app_context():
            success, error = reset_password_with_token('fake_token', 'password1')
            assert not success
            assert 'Invalid' in error

    def test_no_token_for_google_only_user(self, app):
        with app.app_context():
            from database.mongo import db
            email = f'{TEST_USER_PREFIX}googleonly@test.com'
            db.users.insert_one({
                'user_id': email,
                'google_sub': 'google-sub-123',
                'password_hash': None,
                'login_id': generate_login_id(),
            })
            token = create_password_reset_token(email)
            assert token is None

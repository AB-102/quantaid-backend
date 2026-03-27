"""Integration tests for auth routes (/auth/*)."""

from tests.conftest import TEST_USER_PREFIX


class TestSignup:
    def test_signup_success(self, client):
        res = client.post(
            "/auth/signup",
            json={
                "email": f"{TEST_USER_PREFIX}signup@test.com",
                "password": "password123",
                "name": "Signup Test",
            },
        )
        assert res.status_code == 201
        data = res.get_json()
        assert data["redirect_to"] == "profile-creation"

    def test_signup_short_password(self, client):
        res = client.post(
            "/auth/signup",
            json={
                "email": f"{TEST_USER_PREFIX}short@test.com",
                "password": "short",
            },
        )
        assert res.status_code == 400
        assert "at least 8" in res.get_json()["error"]

    def test_signup_invalid_email(self, client):
        res = client.post(
            "/auth/signup",
            json={
                "email": "notanemail",
                "password": "password123",
            },
        )
        assert res.status_code == 400

    def test_signup_duplicate_email(self, client):
        email = f"{TEST_USER_PREFIX}dupe@test.com"
        client.post(
            "/auth/signup",
            json={
                "email": email,
                "password": "password123",
            },
        )
        res = client.post(
            "/auth/signup",
            json={
                "email": email,
                "password": "password456",
            },
        )
        assert res.status_code == 409


class TestLogin:
    def _create_user(self, client, email, password="password123"):
        client.post(
            "/auth/signup",
            json={
                "email": email,
                "password": password,
                "name": "Test",
            },
        )

    def test_login_success(self, client):
        email = f"{TEST_USER_PREFIX}login@test.com"
        self._create_user(client, email)
        # Log out first (signup auto-logs in)
        client.post("/auth/logout")
        res = client.post(
            "/auth/login",
            json={
                "email": email,
                "password": "password123",
            },
        )
        assert res.status_code == 200
        assert res.get_json()["redirect_to"] == "profile-creation"

    def test_login_wrong_password(self, client):
        email = f"{TEST_USER_PREFIX}loginwrong@test.com"
        self._create_user(client, email)
        client.post("/auth/logout")
        res = client.post(
            "/auth/login",
            json={
                "email": email,
                "password": "wrongpassword",
            },
        )
        assert res.status_code == 401

    def test_login_nonexistent_email(self, client):
        res = client.post(
            "/auth/login",
            json={
                "email": f"{TEST_USER_PREFIX}ghost@test.com",
                "password": "password123",
            },
        )
        assert res.status_code == 401


class TestAuthCheck:
    def test_not_authenticated(self, client):
        res = client.get("/auth/check")
        assert res.status_code == 200
        assert res.get_json()["authenticated"] is False

    def test_authenticated_after_signup(self, client):
        client.post(
            "/auth/signup",
            json={
                "email": f"{TEST_USER_PREFIX}check@test.com",
                "password": "password123",
            },
        )
        res = client.get("/auth/check")
        assert res.status_code == 200
        data = res.get_json()
        assert data["authenticated"] is True
        assert data["email"] == f"{TEST_USER_PREFIX}check@test.com"


class TestLogout:
    def test_logout(self, client):
        client.post(
            "/auth/signup",
            json={
                "email": f"{TEST_USER_PREFIX}logout@test.com",
                "password": "password123",
            },
        )
        res = client.post("/auth/logout")
        assert res.status_code == 200
        # Should no longer be authenticated
        check = client.get("/auth/check")
        assert check.get_json()["authenticated"] is False


class TestChangePassword:
    def test_change_password(self, client):
        email = f"{TEST_USER_PREFIX}changepw@test.com"
        client.post(
            "/auth/signup",
            json={
                "email": email,
                "password": "oldpass123",
            },
        )
        res = client.post(
            "/auth/change-password",
            json={
                "current_password": "oldpass123",
                "new_password": "newpass123",
            },
        )
        assert res.status_code == 200
        # Verify new password works
        client.post("/auth/logout")
        res = client.post(
            "/auth/login",
            json={
                "email": email,
                "password": "newpass123",
            },
        )
        assert res.status_code == 200

    def test_change_password_wrong_current(self, client):
        email = f"{TEST_USER_PREFIX}changepw2@test.com"
        client.post(
            "/auth/signup",
            json={
                "email": email,
                "password": "oldpass123",
            },
        )
        res = client.post(
            "/auth/change-password",
            json={
                "current_password": "wrongpass1",
                "new_password": "newpass123",
            },
        )
        assert res.status_code == 401

    def test_change_password_unauthenticated(self, client):
        res = client.post(
            "/auth/change-password",
            json={
                "new_password": "newpass123",
            },
        )
        assert res.status_code == 401


class TestForgotPassword:
    def test_always_returns_200(self, client):
        # Even for nonexistent emails — prevents enumeration
        res = client.post(
            "/auth/forgot-password",
            json={
                "email": f"{TEST_USER_PREFIX}nobody@test.com",
            },
        )
        assert res.status_code == 200

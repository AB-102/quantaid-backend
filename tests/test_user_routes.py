"""Integration tests for user routes (profile, Google SSO)."""

from unittest.mock import MagicMock, patch

from tests.conftest import TEST_USER_PREFIX


def _mock_google_userinfo(email, name="Google User", picture="https://example.com/pic.jpg", sub="google-sub-default"):
    """Return a context manager that mocks the Google userinfo endpoint."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "email": email,
        "name": name,
        "picture": picture,
        "sub": sub,
    }
    return patch("routes.users.http_requests.get", return_value=mock_resp)


class TestGoogleSSO:
    def test_new_google_user(self, client):
        email = f"{TEST_USER_PREFIX}google@test.com"
        with _mock_google_userinfo(email, sub="google-sub-new-123"):
            res = client.post(
                "/append_user_id",
                json={
                    "access_token": "fake-token",
                },
            )
        assert res.status_code == 201
        data = res.get_json()
        assert data["redirect_to"] == "profile-creation"

    def test_returning_google_user(self, client):
        email = f"{TEST_USER_PREFIX}returning@test.com"
        with _mock_google_userinfo(email, name="Returning User", sub="google-sub-returning"):
            # First login
            client.post("/append_user_id", json={"access_token": "fake-token"})
        client.post("/auth/logout")
        with _mock_google_userinfo(email, name="Returning User", sub="google-sub-returning"):
            # Second login
            res = client.post("/append_user_id", json={"access_token": "fake-token"})
        assert res.status_code == 200
        assert res.get_json()["redirect_to"] == "profile-creation"

    def test_implicit_linking_email_then_google(self, client):
        """Email user later logs in with Google → google_sub gets linked."""
        email = f"{TEST_USER_PREFIX}link@test.com"
        # Create via email signup
        signup_res = client.post(
            "/auth/signup",
            json={
                "email": email,
                "password": "password123",
            },
        )
        assert signup_res.status_code == 201
        # Verify user exists before Google login
        from database.mongo import db

        pre_check = db.users.find_one({"user_id": email})
        assert pre_check is not None, f"User {email} not found after signup"
        client.post("/auth/logout")
        # Now log in via Google — should find existing user by email
        with _mock_google_userinfo(email, name="Linked User", sub="google-sub-linked"):
            res = client.post("/append_user_id", json={"access_token": "fake-token"})
        assert res.status_code == 200, f"Expected 200 but got {res.status_code}: {res.get_json()}"
        # Verify the google_sub was linked
        user = db.users.find_one({"user_id": email})
        assert user is not None, f"User {email} not found after Google login"
        assert user["google_sub"] == "google-sub-linked"

    def test_missing_access_token(self, client):
        res = client.post(
            "/append_user_id",
            json={
                "name": "No Token",
            },
        )
        assert res.status_code == 400

    def test_disabled_user_blocked(self, client):
        email = f"{TEST_USER_PREFIX}disabled@test.com"
        with _mock_google_userinfo(email, sub="google-sub-disabled"):
            client.post("/append_user_id", json={"access_token": "fake-token"})
        from database.mongo import db

        db.users.update_one({"user_id": email}, {"$set": {"disabled": True}})
        client.post("/auth/logout")
        with _mock_google_userinfo(email, sub="google-sub-disabled"):
            res = client.post("/append_user_id", json={"access_token": "fake-token"})
        assert res.status_code == 403


class TestProfile:
    def _login(self, client):
        email = f"{TEST_USER_PREFIX}profile@test.com"
        client.post(
            "/auth/signup",
            json={
                "email": email,
                "password": "password123",
                "name": "Profile User",
            },
        )
        return email

    def test_save_and_get_profile(self, client):
        self._login(client)
        # Save profile
        res = client.post(
            "/save_profile",
            json={
                "educationCategory": "College",
                "educationLevel": "Sophomore",
                "subjects": ["Computer Science", "Mathematics"],
                "codingExperience": "1-2 year",
                "favoriteHobbies": ["Reading", "Gaming"],
                "customHobbies": "chess",
                "hobbyPersonalization": True,
            },
        )
        assert res.status_code == 200

        # Get profile
        res = client.get("/get_user_profile")
        assert res.status_code == 200
        data = res.get_json()
        assert data["educationCategory"] == "College"
        assert "Computer Science" in data["subjectsStudied"]
        assert data["hobbyPersonalization"] is True
        assert "Reading" in data["favoriteHobbies"]

    def test_get_profile_unauthenticated(self, client):
        res = client.get("/get_user_profile")
        assert res.status_code == 401

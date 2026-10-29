"""Google SSO login, the auth cookie, and the login_id check behind every authenticated request."""

from tests.conftest import TEST_GOOGLE_CLIENT_ID, TEST_PREFIX

EMAIL = f"{TEST_PREFIX}google@test.com"
SUB = "sub-google-1"


def _google_login(client, google_userinfo, email=EMAIL, sub=SUB, **userinfo):
    google_userinfo(email=email, sub=sub, **userinfo)
    return client.post("/api/auth/google", json={"accessToken": "fake-token"})


class TestGoogleLogin:
    def test_new_user_is_created_and_signed_in(self, client, google_userinfo, test_db):
        res = _google_login(client, google_userinfo)
        assert res.status_code == 201
        assert res.json() == {
            "message": "User created",
            "redirectTo": "profile-creation",
            "isAdmin": False,
            "email": EMAIL,
        }
        user = test_db.users.find_one({"user_id": EMAIL})
        assert user["google_sub"] == SUB
        assert client.get("/api/auth/session").json() == {"authenticated": True, "email": EMAIL, "isAdmin": False}

    def test_new_user_gets_a_welcome_email(self, client, google_userinfo, monkeypatch):
        sent = []
        monkeypatch.setattr("routers.auth.send_welcome_email", lambda to, name: sent.append((to, name)))
        _google_login(client, google_userinfo, name="Ada Lovelace")
        assert sent == [(EMAIL, "Ada Lovelace")]

    def test_returning_user_gets_no_welcome_email(self, client, google_userinfo, test_db, monkeypatch):
        sent = []
        monkeypatch.setattr("routers.auth.send_welcome_email", lambda to, name: sent.append((to, name)))
        test_db.users.insert_one({"user_id": EMAIL, "google_sub": SUB})
        _google_login(client, google_userinfo)
        assert sent == []

    def test_returning_user_with_a_profile_goes_to_the_map(self, client, google_userinfo, test_db):
        test_db.users.insert_one(
            {"user_id": EMAIL, "google_sub": SUB, "login_id": "old", "profile_complete": True, "name": "Kept Name"}
        )
        res = _google_login(client, google_userinfo, name="New Name")
        assert res.status_code == 200
        assert res.json()["redirectTo"] == "map"
        user = test_db.users.find_one({"user_id": EMAIL})
        assert user["login_id"] != "old"
        assert user["name"] == "Kept Name"
        assert "lastLoginAt" in user

    def test_existing_account_is_linked_to_google_by_email(self, client, google_userinfo, test_db):
        test_db.users.insert_one({"user_id": EMAIL, "login_id": "old"})
        res = _google_login(client, google_userinfo)
        assert res.status_code == 200
        assert test_db.users.find_one({"user_id": EMAIL})["google_sub"] == SUB

    def test_pending_google_sub_is_replaced(self, client, google_userinfo, test_db):
        test_db.users.insert_one({"user_id": EMAIL, "google_sub": "pending:abc"})
        _google_login(client, google_userinfo)
        assert test_db.users.find_one({"user_id": EMAIL})["google_sub"] == SUB

    def test_uploaded_picture_is_kept_and_google_picture_is_followed(self, client, google_userinfo, test_db):
        old_form = f"{TEST_PREFIX}old-form@test.com"
        other = f"{TEST_PREFIX}other@test.com"
        test_db.users.insert_one(
            {"user_id": EMAIL, "google_sub": SUB, "picture": "/api/files/0123456789abcdef01234567"}
        )
        test_db.users.insert_one(
            {"user_id": old_form, "google_sub": "sub-old", "picture": "/file/0123456789abcdef01234567"}
        )
        test_db.users.insert_one({"user_id": other, "google_sub": "sub-other", "picture": "https://old.example/p.jpg"})
        new_picture = "https://google.example/new.jpg"
        _google_login(client, google_userinfo, picture=new_picture)
        _google_login(client, google_userinfo, email=old_form, sub="sub-old", picture=new_picture)
        _google_login(client, google_userinfo, email=other, sub="sub-other", picture=new_picture)
        assert test_db.users.find_one({"user_id": EMAIL})["picture"] == "/api/files/0123456789abcdef01234567"
        # Uploads stored before the /api/files rename are still recognised as uploads
        assert test_db.users.find_one({"user_id": old_form})["picture"] == "/file/0123456789abcdef01234567"
        assert test_db.users.find_one({"user_id": other})["picture"] == new_picture

    def test_changed_google_email_signs_in_to_the_existing_account(self, client, google_userinfo, test_db):
        test_db.users.insert_one({"user_id": EMAIL, "google_sub": SUB})
        res = _google_login(client, google_userinfo, email=f"{TEST_PREFIX}new-address@test.com")
        assert res.json()["email"] == EMAIL
        assert client.get("/api/auth/session").json()["email"] == EMAIL

    def test_disabled_account_is_blocked(self, client, google_userinfo, test_db):
        test_db.users.insert_one({"user_id": EMAIL, "google_sub": SUB, "disabled": True})
        res = _google_login(client, google_userinfo)
        assert res.status_code == 403
        assert "quantaid_token" not in res.cookies

    def test_rejected_google_token(self, client, google_userinfo):
        google_userinfo(status_code=401)
        res = client.post("/api/auth/google", json={"accessToken": "expired"})
        assert res.status_code == 401

    def test_missing_access_token(self, client):
        assert client.post("/api/auth/google", json={}).status_code == 422

    def test_first_time_test_user_always_goes_to_onboarding(self, client, google_userinfo, test_db, monkeypatch):
        monkeypatch.setattr("services.google_auth_service.FIRST_TIME_USER_EMAIL", EMAIL)
        test_db.users.insert_one({"user_id": EMAIL, "google_sub": SUB, "profile_complete": True})
        res = _google_login(client, google_userinfo)
        assert res.status_code == 200
        assert res.json()["redirectTo"] == "profile-creation"

    def test_token_issued_to_another_app_is_rejected(self, client, google_userinfo, test_db):
        res = _google_login(client, google_userinfo, aud="another-apps-client-id")
        assert res.status_code == 401
        assert test_db.users.find_one({"user_id": EMAIL}) is None


class TestDeploymentSignIn:
    def test_config_on_a_google_deployment(self, client):
        assert client.get("/api/auth/config").json() == {
            "isRiceDeployment": False,
            "googleClientId": TEST_GOOGLE_CLIENT_ID,
        }

    def test_rice_sign_in_is_off_on_a_google_deployment(self, client):
        assert client.get("/api/auth/rice/login").status_code == 404
        assert client.get("/api/auth/rice/callback").status_code == 404

    def test_google_sign_in_is_off_on_a_rice_deployment(self, client, google_userinfo, test_db, monkeypatch):
        monkeypatch.setattr("routers.auth.IS_RICE_DEPLOYMENT", True)
        res = _google_login(client, google_userinfo)
        assert res.status_code == 404
        assert test_db.users.find_one({"user_id": EMAIL}) is None

    def test_rice_login_waits_for_rice_oidc_credentials(self, client, monkeypatch):
        monkeypatch.setattr("routers.auth.IS_RICE_DEPLOYMENT", True)
        assert client.get("/api/auth/rice/login").status_code == 503


class TestSession:
    def test_logout_invalidates_the_old_cookie(self, client, login_as):
        login_as("logout")
        old_token = client.cookies.get("quantaid_token")
        assert client.post("/api/auth/logout").status_code == 200
        client.cookies.clear()
        client.cookies.set("quantaid_token", old_token)
        assert client.get("/api/auth/session").json() == {"authenticated": False}

    def test_signing_in_again_ends_the_previous_session(self, client, google_userinfo):
        _google_login(client, google_userinfo)
        first_token = client.cookies.get("quantaid_token")
        client.cookies.clear()
        _google_login(client, google_userinfo)
        client.cookies.clear()
        client.cookies.set("quantaid_token", first_token)
        assert client.get("/api/me/profile").status_code == 401

    def test_disabled_user_is_signed_out(self, client, login_as, test_db):
        email = login_as("disabled")
        test_db.users.update_one({"user_id": email}, {"$set": {"disabled": True}})
        assert client.get("/api/me/profile").status_code == 401

    def test_garbage_cookie_is_unauthenticated(self, client):
        client.cookies.set("quantaid_token", "not-a-jwt")
        assert client.get("/api/auth/session").json() == {"authenticated": False}
        assert client.get("/api/me/profile").status_code == 401

    def test_admin_routes_need_an_admin(self, client, login_as):
        assert client.get("/api/admin/users").status_code == 401
        login_as("student")
        assert client.get("/api/admin/users").status_code == 403

    def test_admin_status_comes_from_the_database(self, client, login_as, test_db):
        email = login_as("demoted", is_admin=True)
        assert client.get("/api/admin/users").status_code == 200
        test_db.users.update_one({"user_id": email}, {"$set": {"is_admin": False}})
        assert client.get("/api/admin/users").status_code == 403


class TestAuthCookie:
    def test_cookie_is_samesite_lax_by_default(self, client, google_userinfo):
        res = _google_login(client, google_userinfo)
        assert "samesite=lax" in res.headers["set-cookie"].lower()

    def test_cross_site_deployments_use_samesite_none(self, client, google_userinfo, monkeypatch):
        monkeypatch.setattr("routers.auth.COOKIE_SAMESITE", "none")
        res = _google_login(client, google_userinfo)
        assert "samesite=none" in res.headers["set-cookie"].lower()

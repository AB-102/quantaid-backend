"""Rice SSO: the authorization code flow, every check on Rice's answer, and how a Rice identity maps to an account."""

import base64
import hashlib
import time
from urllib.parse import parse_qs, urlparse

import jwt
import pytest

from config import JWT_SECRET_KEY
from core.jwt import create_rice_flow_token, decode_rice_flow_token
from services.rice_auth_service import RICE_AUTHORIZE_URL
from tests.conftest import (
    TEST_FRONTEND_URL,
    TEST_PREFIX,
    TEST_RICE_CLIENT_ID,
    TEST_RICE_CLIENT_SECRET,
    TEST_RICE_REDIRECT_URI,
    UNPUBLISHED_KEY,
)

EMAIL = f"{TEST_PREFIX}netid@rice.edu"
SUB = "rice-sub-1"
FLOW_COOKIE = "quantaid_rice_oidc"


@pytest.fixture(autouse=True)
def rice_deployment(monkeypatch):
    monkeypatch.setattr("routers.auth.IS_RICE_DEPLOYMENT", True)


def _start_sign_in(client) -> dict:
    """Click "I'm a Rice Student": returns the parameters of the authorize URL the backend sent the browser to."""
    res = client.get("/api/auth/rice/login", follow_redirects=False)
    assert res.status_code == 302
    return {name: values[0] for name, values in parse_qs(urlparse(res.headers["location"]).query).items()}


def _finish_sign_in(client, state: str, code: str = "rice-auth-code"):
    return client.get("/api/auth/rice/callback", params={"code": code, "state": state}, follow_redirects=False)


def _sign_in(client, rice_idp, email=EMAIL, sub=SUB, **idp):
    """The whole round trip: start, Rice signs the user in, and the callback finishes."""
    authorize = _start_sign_in(client)
    rice_idp(email=email, sub=sub, nonce=authorize["nonce"], **idp)
    return _finish_sign_in(client, authorize["state"])


def _failed_with(res, code: str) -> bool:
    return res.status_code == 302 and res.headers["location"] == f"{TEST_FRONTEND_URL}/#/?rice_error={code}"


class TestStartSignIn:
    def test_login_sends_the_browser_to_rice_with_state_nonce_and_pkce(self, client):
        res = client.get("/api/auth/rice/login", follow_redirects=False)
        assert res.status_code == 302
        location = urlparse(res.headers["location"])
        assert f"{location.scheme}://{location.netloc}{location.path}" == RICE_AUTHORIZE_URL
        params = {name: values[0] for name, values in parse_qs(location.query).items()}

        flow = decode_rice_flow_token(client.cookies[FLOW_COOKIE])
        assert flow is not None
        verifier_hash = hashlib.sha256(flow["code_verifier"].encode()).digest()
        assert params == {
            "response_type": "code",
            "client_id": TEST_RICE_CLIENT_ID,
            "redirect_uri": TEST_RICE_REDIRECT_URI,
            "scope": "openid profile email",
            "state": flow["state"],
            "nonce": flow["nonce"],
            "code_challenge": base64.urlsafe_b64encode(verifier_hash).rstrip(b"=").decode(),
            "code_challenge_method": "S256",
        }

    def test_the_flow_cookie_is_short_lived_and_scoped_to_rice_sign_in(self, client):
        res = client.get("/api/auth/rice/login", follow_redirects=False)
        cookie = res.headers["set-cookie"]
        assert cookie.startswith(f"{FLOW_COOKIE}=")
        for flag in ("HttpOnly", "Max-Age=600", "Path=/api/auth/rice", "SameSite=lax"):
            assert flag in cookie

    def test_a_flow_token_is_not_a_sign_in(self, client):
        client.cookies.set("quantaid_token", create_rice_flow_token("state", "nonce", "verifier"))
        assert client.get("/api/auth/session").json() == {"authenticated": False}


class TestSignIn:
    def test_new_user_is_created_signed_in_and_sent_to_onboarding(self, client, rice_idp, test_db, monkeypatch):
        sent = []
        monkeypatch.setattr("routers.auth.send_welcome_email", lambda to, name: sent.append((to, name)))
        authorize = _start_sign_in(client)
        flow = decode_rice_flow_token(client.cookies[FLOW_COOKIE])
        assert flow is not None
        requests = rice_idp(email=EMAIL, sub=SUB, nonce=authorize["nonce"])

        res = _finish_sign_in(client, authorize["state"])

        assert res.status_code == 302
        assert res.headers["location"] == f"{TEST_FRONTEND_URL}/#/profile-creation"
        assert FLOW_COOKIE not in client.cookies
        assert client.get("/api/auth/session").json() == {"authenticated": True, "email": EMAIL, "isAdmin": False}
        user = test_db.users.find_one({"user_id": EMAIL})
        assert user["rice_sub"] == SUB
        assert user["name"] == "Rice User"
        assert sent == [(EMAIL, "Rice User")]
        # client_secret_basic with form-encoded credentials, and the PKCE verifier from this browser's flow cookie
        assert requests["token"]["auth"] == ("test-rice-client-id", "test%20rice%3Asecret%2F%2B")
        assert requests["token"]["data"] == {
            "grant_type": "authorization_code",
            "code": "rice-auth-code",
            "redirect_uri": TEST_RICE_REDIRECT_URI,
            "code_verifier": flow["code_verifier"],
        }
        assert requests["userinfo"]["headers"] == {"Authorization": "Bearer rice-access-token"}

    def test_returning_user_goes_to_the_map(self, client, rice_idp, test_db, monkeypatch):
        sent = []
        monkeypatch.setattr("routers.auth.send_welcome_email", lambda to, name: sent.append((to, name)))
        test_db.users.insert_one({"user_id": EMAIL, "rice_sub": SUB, "profile_complete": True, "login_id": "old"})

        res = _sign_in(client, rice_idp)

        assert res.headers["location"] == f"{TEST_FRONTEND_URL}/#/map"
        assert sent == []
        user = test_db.users.find_one({"user_id": EMAIL})
        assert user["login_id"] != "old"  # signs out other sessions
        assert "lastLoginAt" in user

    def test_admin_goes_to_the_admin_dashboard(self, client, rice_idp, test_db, monkeypatch):
        monkeypatch.setattr("services.rice_auth_service.ADMIN_EMAILS", {EMAIL})
        test_db.users.insert_one({"user_id": EMAIL, "rice_sub": SUB, "profile_complete": True})
        assert _sign_in(client, rice_idp).headers["location"] == f"{TEST_FRONTEND_URL}/#/admin-dashboard"

    def test_aud_may_be_a_list_of_just_this_client(self, client, rice_idp):
        res = _sign_in(client, rice_idp, claims={"aud": [TEST_RICE_CLIENT_ID]})
        assert res.headers["location"] == f"{TEST_FRONTEND_URL}/#/profile-creation"

    def test_name_falls_back_to_given_and_family_name(self, client, rice_idp, test_db):
        _sign_in(client, rice_idp, name=None, userinfo={"given_name": "Ada", "family_name": "Lovelace"})
        assert test_db.users.find_one({"user_id": EMAIL})["name"] == "Ada Lovelace"

    def test_an_account_with_this_email_and_no_rice_link_is_linked(self, client, rice_idp, test_db):
        test_db.users.insert_one({"user_id": EMAIL, "name": "Kept", "profile_complete": True})
        res = _sign_in(client, rice_idp)
        assert res.headers["location"] == f"{TEST_FRONTEND_URL}/#/map"
        user = test_db.users.find_one({"user_id": EMAIL})
        assert user["rice_sub"] == SUB
        assert user["name"] == "Kept"

    def test_the_test_user_always_goes_to_onboarding(self, client, rice_idp, test_db, monkeypatch):
        monkeypatch.setattr("services.rice_auth_service.FIRST_TIME_USER_EMAIL", EMAIL)
        test_db.users.insert_one({"user_id": EMAIL, "rice_sub": SUB, "profile_complete": True})
        assert _sign_in(client, rice_idp).headers["location"] == f"{TEST_FRONTEND_URL}/#/profile-creation"


class TestRefusedAccounts:
    def test_a_disabled_account_is_refused(self, client, rice_idp, test_db):
        test_db.users.insert_one({"user_id": EMAIL, "rice_sub": SUB, "disabled": True})
        res = _sign_in(client, rice_idp)
        assert _failed_with(res, "disabled")
        assert "quantaid_token" not in client.cookies

    def test_an_email_linked_to_another_rice_identity_is_refused(self, client, rice_idp, test_db):
        # A reissued address must never reach the previous holder's records
        test_db.users.insert_one({"user_id": EMAIL, "rice_sub": "someone-else"})
        res = _sign_in(client, rice_idp)
        assert _failed_with(res, "conflict")
        assert "quantaid_token" not in client.cookies
        assert test_db.users.find_one({"user_id": EMAIL})["rice_sub"] == "someone-else"


class TestRefusedCallbacks:
    """Each of these ends on the login page with rice_error=failed, with no account and no sign-in."""

    def _assert_failed(self, client, test_db, res):
        assert _failed_with(res, "failed")
        assert "quantaid_token" not in client.cookies
        assert FLOW_COOKIE not in client.cookies
        assert test_db.users.find_one({"user_id": EMAIL}) is None

    def test_rice_reports_an_error(self, client, test_db):
        _start_sign_in(client)
        res = client.get(
            "/api/auth/rice/callback",
            params={"error": "access_denied", "error_description": "<script>alert(1)</script>"},
            follow_redirects=False,
        )
        self._assert_failed(client, test_db, res)
        assert "script" not in res.headers["location"]

    def test_state_does_not_match(self, client, rice_idp, test_db):
        authorize = _start_sign_in(client)
        rice_idp(email=EMAIL, sub=SUB, nonce=authorize["nonce"])
        self._assert_failed(client, test_db, _finish_sign_in(client, "a-state-from-another-sign-in"))

    def test_no_flow_cookie(self, client, rice_idp, test_db):
        authorize = _start_sign_in(client)
        rice_idp(email=EMAIL, sub=SUB, nonce=authorize["nonce"])
        client.cookies.clear()
        self._assert_failed(client, test_db, _finish_sign_in(client, authorize["state"]))

    def test_expired_flow_cookie(self, client, rice_idp, test_db):
        # Everything else about this sign-in would succeed
        rice_idp(email=EMAIL, sub=SUB, nonce="nonce")
        flow = {"aud": "rice-oidc-flow", "state": "state", "nonce": "nonce", "code_verifier": "verifier"}
        expired = jwt.encode({**flow, "exp": int(time.time()) - 60}, JWT_SECRET_KEY, algorithm="HS256")
        res = client.get(
            "/api/auth/rice/callback",
            params={"code": "rice-auth-code", "state": "state"},
            headers={"Cookie": f"{FLOW_COOKIE}={expired}"},
            follow_redirects=False,
        )
        self._assert_failed(client, test_db, res)

    @pytest.mark.parametrize(
        "idp",
        [
            pytest.param({"token_status": 400}, id="token endpoint refuses the code"),
            pytest.param({"claims": {"nonce": "another-sign-in"}}, id="nonce from another sign-in"),
            pytest.param({"claims": {"nonce": None}}, id="no nonce"),
            pytest.param({"claims": {"aud": "another-client"}}, id="issued to another client"),
            pytest.param({"claims": {"aud": [TEST_RICE_CLIENT_ID, "another-client"]}}, id="also for another client"),
            pytest.param({"claims": {"iss": "https://idp.example.com"}}, id="another issuer"),
            pytest.param(
                {"claims": {"iat": int(time.time()) - 7200, "exp": int(time.time()) - 3600}}, id="expired ID token"
            ),
            pytest.param({"signing_key": UNPUBLISHED_KEY}, id="signed with a key Rice didn't publish"),
            pytest.param(
                {"signing_key": TEST_RICE_CLIENT_SECRET, "algorithm": "HS256"},
                id="HS256 with the client secret",
                # PyJWT warns that the test secret is a short HMAC key
                marks=pytest.mark.filterwarnings("ignore::jwt.warnings.InsecureKeyLengthWarning"),
            ),
            pytest.param({"userinfo": {"sub": "someone-else"}}, id="userinfo describes someone else"),
            pytest.param({"userinfo": {"email": ""}}, id="userinfo has no email"),
        ],
    )
    def test_rice_answer_fails_a_check(self, client, rice_idp, test_db, idp):
        self._assert_failed(client, test_db, _sign_in(client, rice_idp, **idp))


class TestOffRice:
    def test_rice_sign_in_is_off_on_a_google_deployment(self, client, monkeypatch):
        monkeypatch.setattr("routers.auth.IS_RICE_DEPLOYMENT", False)
        assert client.get("/api/auth/rice/login", follow_redirects=False).status_code == 404
        assert client.get("/api/auth/rice/callback", follow_redirects=False).status_code == 404

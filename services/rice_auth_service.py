"""
Rice SSO: the OIDC authorization code flow against Rice's Shibboleth IdP, and resolving its result to a Quantaid user.

The endpoints come from https://idp.rice.edu/.well-known/openid-configuration.
"""

import base64
import hashlib
import secrets
from datetime import UTC, datetime
from urllib.parse import quote, urlencode

import httpx
import jwt
from pydantic import BaseModel
from pymongo.asynchronous.database import AsyncDatabase

from config import (
    ADMIN_EMAILS,
    FIRST_TIME_USER_EMAIL,
    RICE_OIDC_CLIENT_ID,
    RICE_OIDC_CLIENT_SECRET,
    RICE_OIDC_REDIRECT_URI,
)
from services.login_service import LoginResult, is_disabled, new_user_doc

RICE_ISSUER = "https://idp.rice.edu"
RICE_AUTHORIZE_URL = "https://idp.rice.edu/idp/profile/oidc/authorize"
RICE_TOKEN_URL = "https://idp.rice.edu/idp/profile/oidc/token"
RICE_USERINFO_URL = "https://idp.rice.edu/idp/profile/oidc/userinfo"
RICE_JWKS_URL = "https://idp.rice.edu/idp/profile/oidc/keyset"


class RiceSignInError(Exception):
    """
    A Rice sign-in that can't go on. `code` is all the login page is told: "failed", "disabled" or "conflict".
    The message says which step stopped, for the logs; it never holds tokens, claims or emails.
    """

    def __init__(self, code: str, reason: str):
        super().__init__(reason)
        self.code = code


class RiceIdentity(BaseModel):
    sub: str
    email: str
    name: str | None = None


def code_challenge(code_verifier: str) -> str:
    """The PKCE S256 challenge for a verifier (RFC 7636 §4.2)."""
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def rice_authorization_url(state: str, nonce: str, code_verifier: str) -> str:
    """Where to send the browser to sign in at Rice."""
    params = {
        "response_type": "code",
        "client_id": RICE_OIDC_CLIENT_ID,
        "redirect_uri": RICE_OIDC_REDIRECT_URI,
        "scope": "openid profile email",
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge(code_verifier),
        "code_challenge_method": "S256",
    }
    return f"{RICE_AUTHORIZE_URL}?{urlencode(params)}"


def _verify_id_token(id_token: str, jwks: dict, nonce: str) -> dict:
    """The ID token's claims, once its signature and claims check out (OIDC Core 3.1.3.7)."""
    try:
        kid = jwt.get_unverified_header(id_token).get("kid")
        if not isinstance(kid, str):
            raise RiceSignInError("failed", "ID token names no signing key")
        key = jwt.PyJWKSet.from_dict(jwks)[kid]
        claims = jwt.decode(
            id_token,
            key=key,
            # Pinned: Rice also offers HS256, which would be signed with the client secret
            algorithms=["RS256"],
            audience=RICE_OIDC_CLIENT_ID,
            issuer=RICE_ISSUER,
            leeway=60,
            options={"require": ["exp", "iat", "iss", "aud", "sub", "nonce"]},
        )
    except (jwt.PyJWTError, KeyError) as err:
        raise RiceSignInError("failed", f"ID token rejected ({type(err).__name__})") from err
    # jwt.decode only checks that aud includes us; a token also issued to other clients must be rejected too
    if claims["aud"] != RICE_OIDC_CLIENT_ID and claims["aud"] != [RICE_OIDC_CLIENT_ID]:
        raise RiceSignInError("failed", "ID token is also issued to other clients")
    if not secrets.compare_digest(str(claims["nonce"]).encode(), nonce.encode()):
        raise RiceSignInError("failed", "ID token nonce doesn't match this sign-in")
    return claims


async def fetch_rice_identity(code: str, code_verifier: str, nonce: str) -> RiceIdentity:
    """
    Exchange the authorization code, verify the ID token, and read the user's claims from userinfo.
    Raises RiceSignInError("failed") if any step fails. Rice's tokens are dropped once this returns.
    """
    # client_secret_basic: the ID and secret are URL-encoded before going into the Basic header (RFC 6749 §2.3.1)
    client_auth = (quote(RICE_OIDC_CLIENT_ID, safe=""), quote(RICE_OIDC_CLIENT_SECRET, safe=""))
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            token_resp = await client.post(
                RICE_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": RICE_OIDC_REDIRECT_URI,
                    "code_verifier": code_verifier,
                },
                auth=client_auth,
            )
            if token_resp.status_code != 200:
                raise RiceSignInError("failed", f"token endpoint answered {token_resp.status_code}")
            tokens = token_resp.json()
            id_token = tokens.get("id_token")
            access_token = tokens.get("access_token")
            if not isinstance(id_token, str) or not isinstance(access_token, str):
                raise RiceSignInError("failed", "token response has no ID token or access token")

            # Fetched each time: sign-ins are rare, so there's no cached key set to go stale when Rice rotates keys
            jwks_resp = await client.get(RICE_JWKS_URL)
            if jwks_resp.status_code != 200:
                raise RiceSignInError("failed", f"key set endpoint answered {jwks_resp.status_code}")
            claims = _verify_id_token(id_token, jwks_resp.json(), nonce)

            # With response_type=code, Rice sends the email and name from userinfo, not in the ID token
            userinfo_resp = await client.get(RICE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
            if userinfo_resp.status_code != 200:
                raise RiceSignInError("failed", f"userinfo endpoint answered {userinfo_resp.status_code}")
            userinfo = userinfo_resp.json()
    except (httpx.HTTPError, ValueError) as err:
        # Unreachable IdP, timeout, or a body that isn't JSON (such as a signed userinfo response)
        raise RiceSignInError("failed", f"talking to Rice failed ({type(err).__name__})") from err

    # OIDC Core 5.3.2: userinfo has to describe the same user the ID token is about
    if userinfo.get("sub") != claims["sub"]:
        raise RiceSignInError("failed", "userinfo sub doesn't match the ID token")
    email = str(userinfo.get("email") or "").lower()
    if not email:
        raise RiceSignInError("failed", "userinfo has no email")
    full_name = " ".join(part for part in (userinfo.get("given_name"), userinfo.get("family_name")) if part)
    return RiceIdentity(sub=claims["sub"], email=email, name=userinfo.get("name") or full_name or None)


async def resolve_or_create_rice_user(identity: RiceIdentity, db: AsyncDatabase) -> LoginResult:
    """
    Find or create the user for a Rice identity and start a new login.

    Identity resolution: match rice_sub; else link the account with this email, but only if it has no rice_sub yet;
    else create one. An email already linked to a different rice_sub is refused ("conflict"), so a reissued address
    or NetID can never reach another person's records (FERPA). Every login rotates login_id, which signs the user out
    of their other sessions. FIRST_TIME_USER_EMAIL is a dev/test account that is always sent to onboarding.
    """
    is_admin = identity.email in ADMIN_EMAILS
    login_id = secrets.token_hex(32)
    is_test_user = identity.email == FIRST_TIME_USER_EMAIL

    existing = await db.users.find_one({"rice_sub": identity.sub})
    if existing is None:
        existing = await db.users.find_one({"user_id": identity.email})
        if existing is not None and existing.get("rice_sub"):
            raise RiceSignInError("conflict", "the account with this email is linked to another Rice identity")

    if existing is None:
        await db.users.insert_one(
            {**new_user_doc(identity.email, identity.name, login_id, is_admin), "rice_sub": identity.sub}
        )
        return LoginResult(
            email=identity.email,
            login_id=login_id,
            is_admin=is_admin,
            redirect_to="profile-creation",
            message="Test user" if is_test_user else "User created",
            created=not is_test_user,
        )

    if is_disabled(existing):
        raise RiceSignInError("disabled", "the account is disabled")
    update = {"login_id": login_id, "is_admin": is_admin, "lastLoginAt": datetime.now(UTC), "rice_sub": identity.sub}
    if identity.name and not existing.get("name"):
        update["name"] = identity.name
    await db.users.update_one({"_id": existing["_id"]}, {"$set": update})
    # The stored user_id is the account's identity, even if the Rice email has since changed
    return LoginResult(
        email=existing["user_id"],
        login_id=login_id,
        is_admin=is_admin,
        redirect_to="map" if existing.get("profile_complete") and not is_test_user else "profile-creation",
        message="Test user" if is_test_user else "Logged in",
    )

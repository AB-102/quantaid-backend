"""Rice University SSO authentication via OIDC authorization code flow.

Endpoints:
    GET /auth/rice/login    — Redirects browser to Rice IdP for authentication
    GET /auth/rice/callback — Receives authorization code, exchanges for tokens,
                              creates or links user, redirects to frontend
"""

import base64
import json
import secrets
from datetime import UTC, datetime
from urllib.parse import urlencode

import requests as http_requests
from flask import Blueprint, redirect, request, session
from flask_login import login_user

from config import (
    ADMIN_EMAILS,
    FRONTEND_URL,
    RICE_OIDC_CLIENT_ID,
    RICE_OIDC_CLIENT_SECRET,
    RICE_OIDC_REDIRECT_URI,
)
from database.mongo import db
from models.user import User
from services.auth_service import generate_login_id

rice_auth_bp = Blueprint("rice_auth", __name__, url_prefix="/auth/rice")

# Rice IdP OIDC endpoints (from https://idp.rice.edu/.well-known/openid-configuration)
_RICE_AUTHORIZE_URL = "https://idp.rice.edu/idp/profile/oidc/authorize"
_RICE_TOKEN_URL = "https://idp.rice.edu/idp/profile/oidc/token"
_RICE_USERINFO_URL = "https://idp.rice.edu/idp/profile/oidc/userinfo"


def _decode_id_token_payload(id_token: str) -> dict:
    # Decode the JWT payload without signature verification.
    # Safe here because the token was received directly from Rice IdP over HTTPS.
    payload_b64 = id_token.split(".")[1]
    payload_b64 += "=" * (4 - len(payload_b64) % 4)
    return json.loads(base64.urlsafe_b64decode(payload_b64))


@rice_auth_bp.route("/login", methods=["GET"])
def rice_login():
    """Redirect the user's browser to Rice IdP for OIDC authentication."""
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)

    # Store in session so we can validate on callback
    session["rice_oidc_state"] = state
    session["rice_oidc_nonce"] = nonce

    params = {
        "client_id": RICE_OIDC_CLIENT_ID,
        "redirect_uri": RICE_OIDC_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid profile email",
        "state": state,
        "nonce": nonce,
    }
    return redirect(f"{_RICE_AUTHORIZE_URL}?{urlencode(params)}")


@rice_auth_bp.route("/callback", methods=["GET"])
def rice_callback():
    """Handle the OIDC callback from Rice IdP after user authentication."""
    error = request.args.get("error")
    if error:
        error_desc = request.args.get("error_description", "Unknown error")
        return redirect(f"{FRONTEND_URL}/#/?{urlencode({'rice_error': error_desc})}")

    code = request.args.get("code")
    state = request.args.get("state")

    # Validate state to prevent CSRF
    expected_state = session.pop("rice_oidc_state", None)
    expected_nonce = session.pop("rice_oidc_nonce", None)

    if not code or not state or state != expected_state:
        return redirect(f"{FRONTEND_URL}/#/?rice_error=invalid_state")

    # Exchange authorization code for tokens
    token_response = http_requests.post(
        _RICE_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": RICE_OIDC_REDIRECT_URI,
            "client_id": RICE_OIDC_CLIENT_ID,
            "client_secret": RICE_OIDC_CLIENT_SECRET,
        },
        headers={"Accept": "application/json"},
        timeout=10,
    )

    if token_response.status_code != 200:
        return redirect(f"{FRONTEND_URL}/#/?rice_error=token_exchange_failed")

    tokens = token_response.json()
    access_token = tokens.get("access_token")
    if not access_token:
        return redirect(f"{FRONTEND_URL}/#/?rice_error=no_access_token")

    # Validate nonce in the id_token to prevent replay attacks
    id_token = tokens.get("id_token")
    if id_token:
        try:
            claims = _decode_id_token_payload(id_token)
            if claims.get("nonce") != expected_nonce:
                return redirect(f"{FRONTEND_URL}/#/?rice_error=invalid_nonce")
        except Exception:
            return redirect(f"{FRONTEND_URL}/#/?rice_error=invalid_id_token")

    # Fetch user info from Rice IdP
    userinfo_response = http_requests.get(
        _RICE_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )

    if userinfo_response.status_code != 200:
        return redirect(f"{FRONTEND_URL}/#/?rice_error=userinfo_failed")

    userinfo = userinfo_response.json()
    email = (userinfo.get("email") or "").strip().lower()
    rice_sub = userinfo.get("sub", "")
    name = userinfo.get("name") or ""
    if not name:
        given = userinfo.get("given_name", "")
        family = userinfo.get("family_name", "")
        name = f"{given} {family}".strip()

    if not email or not rice_sub:
        return redirect(f"{FRONTEND_URL}/#/?rice_error=missing_user_info")

    # --- Identity resolution (same pattern as Google SSO) ---

    is_admin = email in ADMIN_EMAILS

    # Priority 1: Match by rice_sub (returning Rice SSO user)
    user_doc = db.users.find_one({"rice_sub": rice_sub})

    # Priority 2: Match by email (implicit linking — email-signup or Google user now using Rice SSO)
    if not user_doc:
        user_doc = db.users.find_one({"user_id": email})

    if user_doc:
        # Existing user — check disabled
        if user_doc.get("disabled", False):
            return redirect(f"{FRONTEND_URL}/#/?rice_error=account_disabled")

        # Rotate login_id to invalidate other sessions
        new_login_id = generate_login_id()
        update_fields: dict = {
            "login_id": new_login_id,
            "is_admin": is_admin,
            "lastLoginAt": datetime.now(UTC),
        }

        # Link Rice account if not already linked
        if not user_doc.get("rice_sub"):
            update_fields["rice_sub"] = rice_sub

        # Update name if not set
        if not user_doc.get("name") and name:
            update_fields["name"] = name

        db.users.update_one({"_id": user_doc["_id"]}, {"$set": update_fields})

        user_doc["login_id"] = new_login_id
        user_doc["is_admin"] = is_admin
        user = User(user_doc)
        login_user(user)
        session["login_id"] = new_login_id

        redirect_to = "map" if user.profile_complete else "profile-creation"
    else:
        # New user — create account
        new_login_id = generate_login_id()
        new_user_doc = {
            "user_id": email,
            "name": name,
            "rice_sub": rice_sub,
            "google_sub": None,
            "password_hash": None,
            "login_id": new_login_id,
            "is_admin": is_admin,
            "disabled": False,
            "profile_complete": False,
            "unlockedLevels": [0],
            "completedQuizzes": [],
            "hasViewedFirstLesson": False,
            "createdAt": datetime.now(UTC),
        }
        db.users.insert_one(new_user_doc)

        user = User(new_user_doc)
        login_user(user)
        session["login_id"] = new_login_id
        redirect_to = "profile-creation"

    return redirect(f"{FRONTEND_URL}/#/{redirect_to}")

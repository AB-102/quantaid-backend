"""Google SSO: verify a Google access token and resolve it to a Quantaid user."""

import secrets
from datetime import UTC, datetime

import httpx
from fastapi import HTTPException, status
from pydantic import BaseModel
from pymongo.asynchronous.database import AsyncDatabase

from config import ADMIN_EMAILS, FIRST_TIME_USER_EMAIL, GOOGLE_CLIENT_ID
from core.file_urls import uploaded_file_id

GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


class GoogleIdentity(BaseModel):
    sub: str
    email: str
    name: str | None = None
    picture: str | None = None


class LoginResult(BaseModel):
    email: str
    login_id: str
    is_admin: bool
    redirect_to: str
    message: str
    created: bool = False


async def verify_google_token(access_token: str) -> GoogleIdentity | None:
    """
    Ask Google who the access token belongs to. Returns None if Google rejects it, the token was issued to
    another app's OAuth client, or Google leaves out email/sub.
    """
    async with httpx.AsyncClient(timeout=10) as client:
        # Without this audience check, a token the user gave any other Google app would sign them in here
        token_info = await client.get(GOOGLE_TOKENINFO_URL, params={"access_token": access_token})
        if token_info.status_code != 200 or token_info.json().get("aud") != GOOGLE_CLIENT_ID:
            return None
        # tokeninfo has no name or picture, so the identity still comes from userinfo
        resp = await client.get(GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
    if resp.status_code != 200:
        return None
    data = resp.json()
    email = data.get("email", "").lower()
    sub = data.get("sub", "")
    if not email or not sub:
        return None
    return GoogleIdentity(sub=sub, email=email, name=data.get("name"), picture=data.get("picture"))


def _new_user_doc(identity: GoogleIdentity, login_id: str, is_admin: bool) -> dict:
    return {
        "user_id": identity.email,
        "name": identity.name,
        "picture": identity.picture,
        "google_sub": identity.sub,
        "login_id": login_id,
        "is_admin": is_admin,
        "profile_complete": False,
        "unlockedLevels": [0],
        "completedQuizzes": [],
        "hasViewedFirstLesson": False,
        "createdAt": datetime.now(UTC),
    }


def _raise_if_disabled(user_doc: dict | None) -> None:
    if user_doc and user_doc.get("disabled", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account has been disabled.")


async def resolve_or_create_user(identity: GoogleIdentity, db: AsyncDatabase) -> LoginResult:
    """
    Find or create the user for a Google identity and start a new login.

    Identity resolution: match google_sub, then email (links an existing account to Google), else create.
    Every login rotates login_id, which signs the user out of their other sessions.
    FIRST_TIME_USER_EMAIL is a dev/test account that is always sent to onboarding.
    """
    is_admin = identity.email in ADMIN_EMAILS
    login_id = secrets.token_hex(32)

    if identity.email == FIRST_TIME_USER_EMAIL:
        user_doc = await db.users.find_one({"user_id": identity.email})
        _raise_if_disabled(user_doc)
        if user_doc is None:
            await db.users.insert_one(_new_user_doc(identity, login_id, is_admin))
        else:
            update: dict = {"login_id": login_id, "is_admin": is_admin}
            if not user_doc.get("google_sub"):
                update["google_sub"] = identity.sub
            await db.users.update_one({"user_id": identity.email}, {"$set": update})
        return LoginResult(
            email=identity.email,
            login_id=login_id,
            is_admin=is_admin,
            redirect_to="profile-creation",
            message="Test user",
        )

    existing = await db.users.find_one({"google_sub": identity.sub})
    if existing is None:
        existing = await db.users.find_one({"user_id": identity.email})

    if existing is None:
        await db.users.insert_one(_new_user_doc(identity, login_id, is_admin))
        return LoginResult(
            email=identity.email,
            login_id=login_id,
            is_admin=is_admin,
            redirect_to="profile-creation",
            message="User created",
            created=True,
        )

    _raise_if_disabled(existing)
    update = {"login_id": login_id, "is_admin": is_admin, "lastLoginAt": datetime.now(UTC)}
    # Link Google, or replace a placeholder sub
    existing_sub = existing.get("google_sub") or ""
    if not existing_sub or existing_sub.startswith("pending:"):
        update["google_sub"] = identity.sub
    # Keep a picture the user uploaded; otherwise follow their Google picture
    if identity.picture and not uploaded_file_id(existing.get("picture")):
        update["picture"] = identity.picture
    if identity.name and not existing.get("name"):
        update["name"] = identity.name
    await db.users.update_one({"user_id": existing["user_id"]}, {"$set": update})
    # The stored user_id is the account's identity, even if the Google email has since changed
    return LoginResult(
        email=existing["user_id"],
        login_id=login_id,
        is_admin=is_admin,
        redirect_to="map" if existing.get("profile_complete") else "profile-creation",
        message="Logged in",
    )

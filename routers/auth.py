import os
import secrets
from datetime import UTC, datetime
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse

from config import ADMIN_EMAILS, FIRST_TIME_USER_EMAIL, JWT_EXPIRE_MINUTES, RICE_OIDC_CLIENT_ID
from core.jwt import create_access_token
from database.motor_client import motor_db
from dependencies.auth import get_optional_user
from schemas.user import GoogleSSORequest, UserOut

GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

router = APIRouter(tags=["Auth"])

_is_production = os.getenv("FLASK_ENV", "").lower() == "production"

# Annotated dependency — avoids Depends() call in function signature default (ruff B008)
OptionalUser = Annotated[UserOut | None, Depends(get_optional_user)]


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="quantaid_token",
        value=token,
        httponly=True,
        secure=_is_production,
        samesite="none" if _is_production else "lax",
        max_age=JWT_EXPIRE_MINUTES * 60,
    )


def _clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key="quantaid_token",
        httponly=True,
        secure=_is_production,
        samesite="none" if _is_production else "lax",
    )


@router.post("/append_user_id")
async def google_login(body: GoogleSSORequest):
    """
    Google SSO login/signup. Async rewrite of Flask routes/users.py:append_user_id.
    Issues a JWT cookie instead of a Flask-Login session.
    """
    async with httpx.AsyncClient(timeout=10) as client:
        google_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {body.access_token}"},
        )
    if google_resp.status_code != 200:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired Google token")

    gd = google_resp.json()
    email: str = gd.get("email", "").lower()
    name: str | None = gd.get("name")
    picture: str | None = gd.get("picture")
    google_sub: str = gd.get("sub", "")

    if not email or not google_sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not verify Google identity")

    is_admin = email in ADMIN_EMAILS

    # Test user: always redirect to onboarding
    if email == FIRST_TIME_USER_EMAIL:
        user_doc = await motor_db.users.find_one({"user_id": email})
        if user_doc and user_doc.get("disabled", False):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account has been disabled.")
        login_id = secrets.token_hex(32)
        if not user_doc:
            await motor_db.users.insert_one({
                "user_id": email, "name": name, "picture": picture, "google_sub": google_sub,
                "login_id": login_id, "is_admin": is_admin, "profile_complete": False,
                "unlockedLevels": [0], "completedQuizzes": [], "hasViewedFirstLesson": False,
                "createdAt": datetime.now(UTC),
            })
        else:
            update: dict = {"login_id": login_id, "is_admin": is_admin}
            if google_sub and not user_doc.get("google_sub"):
                update["google_sub"] = google_sub
            await motor_db.users.update_one({"user_id": email}, {"$set": update})
        token = create_access_token(email, is_admin)
        resp = JSONResponse({
            "message": "Test user", "redirect_to": "profile-creation",
            "is_admin": is_admin, "email": email,
        })
        _set_auth_cookie(resp, token)
        return resp

    # Identity resolution: google_sub → email → create
    existing = await motor_db.users.find_one({"google_sub": google_sub})
    if not existing:
        existing = await motor_db.users.find_one({"user_id": email})

    if existing:
        if existing.get("disabled", False):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account has been disabled.")
        new_login_id = secrets.token_hex(32)
        update = {"login_id": new_login_id, "is_admin": is_admin, "lastLoginAt": datetime.now(UTC)}
        existing_sub = existing.get("google_sub") or ""
        if google_sub and (not existing_sub or existing_sub.startswith("pending:")):
            update["google_sub"] = google_sub
        current_picture = existing.get("picture", "")
        if picture and not (current_picture and "/file/" in current_picture):
            update["picture"] = picture
        if name and not existing.get("name"):
            update["name"] = name
        await motor_db.users.update_one({"user_id": existing["user_id"]}, {"$set": update})
        redirect_to = "map" if existing.get("profile_complete") else "profile-creation"
        token = create_access_token(email, is_admin)
        resp = JSONResponse({
            "message": "Logged in", "redirect_to": redirect_to,
            "is_admin": is_admin, "email": email,
        })
        _set_auth_cookie(resp, token)
        return resp

    # New user
    login_id = secrets.token_hex(32)
    await motor_db.users.insert_one({
        "user_id": email, "name": name, "picture": picture, "google_sub": google_sub,
        "login_id": login_id, "is_admin": is_admin, "profile_complete": False,
        "unlockedLevels": [0], "completedQuizzes": [], "hasViewedFirstLesson": False,
        "createdAt": datetime.now(UTC),
    })
    token = create_access_token(email, is_admin)
    resp = JSONResponse(
        {"message": "User created", "redirect_to": "profile-creation", "is_admin": is_admin, "email": email},
        status_code=201,
    )
    _set_auth_cookie(resp, token)
    return resp


@router.get("/auth/check")
async def check(user: OptionalUser):
    if user:
        return {"authenticated": True, "email": user.email, "is_admin": user.is_admin}
    return {"authenticated": False}


@router.post("/auth/logout")
async def logout(user: OptionalUser):
    if user:
        new_login_id = secrets.token_hex(32)
        await motor_db.users.update_one({"user_id": user.email}, {"$set": {"login_id": new_login_id}})
    resp = JSONResponse({"message": "Logged out successfully."})
    _clear_auth_cookie(resp)
    return resp


@router.get("/auth/rice/callback")
async def rice_oidc_callback():
    if not RICE_OIDC_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rice OIDC not yet configured",
        )
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Rice OIDC token exchange not yet implemented",
    )

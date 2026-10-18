from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status

from core.jwt import decode_access_token
from database.db import db
from schemas.user import UserOut


async def _user_from_token(token: str | None) -> UserOut | None:
    """
    Return the user for a quantaid_token cookie, or None if the token is missing, invalid or stale.

    The token's `lid` must match the user's current login_id. Login and logout rotate login_id,
    so this check is what makes logout and admin "disable user" take effect immediately.
    """
    if not token:
        return None
    payload = decode_access_token(token)
    if payload is None:
        return None
    user_doc = await db.users.find_one({"user_id": payload["sub"]}, {"login_id": 1, "disabled": 1, "is_admin": 1})
    if user_doc is None or user_doc.get("disabled", False):
        return None
    if user_doc.get("login_id") != payload.get("lid"):
        return None
    return UserOut(email=payload["sub"], is_admin=user_doc.get("is_admin", False))


async def get_current_user(quantaid_token: str | None = Cookie(default=None)) -> UserOut:
    user = await _user_from_token(quantaid_token)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


async def get_optional_user(quantaid_token: str | None = Cookie(default=None)) -> UserOut | None:
    return await _user_from_token(quantaid_token)


async def require_admin(user: Annotated[UserOut, Depends(get_current_user)]) -> UserOut:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


# Annotated dependencies — avoid Depends() calls in function signature defaults (ruff B008)
CurrentUser = Annotated[UserOut, Depends(get_current_user)]
OptionalUser = Annotated[UserOut | None, Depends(get_optional_user)]
AdminUser = Annotated[UserOut, Depends(require_admin)]

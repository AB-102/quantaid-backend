from fastapi import Cookie, HTTPException, status

from core.jwt import decode_access_token
from schemas.user import UserOut


async def get_current_user(quantaid_token: str | None = Cookie(default=None)) -> UserOut:
    if not quantaid_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = decode_access_token(quantaid_token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return UserOut(email=payload["sub"], is_admin=payload["is_admin"])


async def get_optional_user(quantaid_token: str | None = Cookie(default=None)) -> UserOut | None:
    if not quantaid_token:
        return None
    payload = decode_access_token(quantaid_token)
    if payload is None:
        return None
    return UserOut(email=payload["sub"], is_admin=payload["is_admin"])

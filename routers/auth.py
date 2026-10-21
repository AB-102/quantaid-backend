import logging
import secrets

from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import JSONResponse

from config import GOOGLE_CLIENT_ID, IS_PRODUCTION, IS_RICE_DEPLOYMENT, JWT_EXPIRE_MINUTES, RICE_OIDC_CLIENT_ID
from core.jwt import create_access_token
from database.db import db
from dependencies.auth import OptionalUser
from schemas.user import GoogleSSORequest
from services.google_auth_service import resolve_or_create_user, verify_google_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Auth"])


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="quantaid_token",
        value=token,
        httponly=True,
        secure=IS_PRODUCTION,
        samesite="none" if IS_PRODUCTION else "lax",
        max_age=JWT_EXPIRE_MINUTES * 60,
    )


def _clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key="quantaid_token",
        httponly=True,
        secure=IS_PRODUCTION,
        samesite="none" if IS_PRODUCTION else "lax",
    )


def _require_rice_deployment() -> None:
    if not IS_RICE_DEPLOYMENT:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Rice sign-in is not available on this deployment"
        )


@router.get("/auth/config")
async def get_auth_config():
    """Which sign-in the login page should offer on this deployment."""
    return {"isRiceDeployment": IS_RICE_DEPLOYMENT, "googleClientId": GOOGLE_CLIENT_ID or None}


@router.post("/auth/google")
async def google_login(body: GoogleSSORequest):
    """Google SSO login/signup. Verifies the Google access token and sets the quantaid_token cookie."""
    if IS_RICE_DEPLOYMENT:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Google sign-in is not available on this deployment"
        )
    identity = await verify_google_token(body.accessToken)
    if identity is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired Google token")
    result = await resolve_or_create_user(identity, db)
    logger.debug("Google login for %s (%s)", result.email, result.message)
    resp = JSONResponse(
        {
            "message": result.message,
            "redirectTo": result.redirect_to,
            "isAdmin": result.is_admin,
            "email": result.email,
        },
        status_code=status.HTTP_201_CREATED if result.created else status.HTTP_200_OK,
    )
    _set_auth_cookie(resp, create_access_token(result.email, result.login_id))
    return resp


@router.get("/auth/session")
async def get_session(user: OptionalUser):
    if user:
        return {"authenticated": True, "email": user.email, "isAdmin": user.is_admin}
    return {"authenticated": False}


@router.post("/auth/logout")
async def logout(user: OptionalUser):
    if user:
        # Rotating login_id invalidates every token issued for this user, on every device
        await db.users.update_one({"user_id": user.email}, {"$set": {"login_id": secrets.token_hex(32)}})
    resp = JSONResponse({"message": "Logged out successfully."})
    _clear_auth_cookie(resp)
    return resp


@router.get("/auth/rice/login")
async def rice_oidc_login():
    """Start Rice SSO. The login page's "I'm a Rice Student" button sends the browser here."""
    _require_rice_deployment()
    if not RICE_OIDC_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rice OIDC not yet configured",
        )
    # TODO(#17): redirect to Rice's authorize endpoint with client_id, redirect_uri, scope, state and nonce
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Rice OIDC login not yet implemented",
    )


@router.get("/auth/rice/callback")
async def rice_oidc_callback():
    _require_rice_deployment()
    if not RICE_OIDC_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rice OIDC not yet configured",
        )
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Rice OIDC token exchange not yet implemented",
    )

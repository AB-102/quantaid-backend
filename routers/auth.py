import logging
import secrets
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Cookie, HTTPException, Response, status
from fastapi.responses import JSONResponse, RedirectResponse

from config import (
    COOKIE_SAMESITE,
    FRONTEND_URL,
    GOOGLE_CLIENT_ID,
    IS_PRODUCTION,
    IS_RICE_DEPLOYMENT,
    JWT_EXPIRE_MINUTES,
)
from core.jwt import RICE_FLOW_MINUTES, create_access_token, create_rice_flow_token, decode_rice_flow_token
from database.db import db
from dependencies.auth import OptionalUser
from schemas.user import GoogleSSORequest
from services.email_service import send_welcome_email
from services.google_auth_service import resolve_or_create_user, verify_google_token
from services.rice_auth_service import (
    RiceSignInError,
    fetch_rice_identity,
    resolve_or_create_rice_user,
    rice_authorization_url,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Auth"])


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="quantaid_token",
        value=token,
        httponly=True,
        secure=IS_PRODUCTION,
        samesite=COOKIE_SAMESITE,
        max_age=JWT_EXPIRE_MINUTES * 60,
    )


def _clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key="quantaid_token",
        httponly=True,
        secure=IS_PRODUCTION,
        samesite=COOKIE_SAMESITE,
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
async def google_login(body: GoogleSSORequest, background_tasks: BackgroundTasks):
    """
    Google SSO login/signup. Verifies the Google access token and sets the quantaid_token cookie.
    A new account also gets a welcome email, sent after the response.
    """
    if IS_RICE_DEPLOYMENT:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Google sign-in is not available on this deployment"
        )
    identity = await verify_google_token(body.accessToken)
    if identity is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired Google token")
    result = await resolve_or_create_user(identity, db)
    logger.debug("Google login for %s (%s)", result.email, result.message)
    if result.created:
        background_tasks.add_task(send_welcome_email, result.email, identity.name)
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


# Rice sign-in keeps its state, nonce and PKCE verifier in this cookie between the two routes below. It's always
# SameSite=Lax, even where COOKIE_SAMESITE is "none": both requests are top-level navigations to the backend.
RICE_FLOW_COOKIE = "quantaid_rice_oidc"
_RICE_FLOW_COOKIE_PATH = "/api/auth/rice"


def _redirect_to_frontend(route: str) -> RedirectResponse:
    """Send the browser to the app (HashRouter), and drop the Rice flow cookie whatever the outcome."""
    # 302, not Starlette's default 307: the browser should GET the app page
    resp = RedirectResponse(f"{FRONTEND_URL}/#/{route}", status_code=status.HTTP_302_FOUND)
    resp.delete_cookie(
        RICE_FLOW_COOKIE, path=_RICE_FLOW_COOKIE_PATH, httponly=True, secure=IS_PRODUCTION, samesite="lax"
    )
    return resp


@router.get("/auth/rice/login")
async def rice_oidc_login():
    """Start Rice SSO. The login page's "I'm a Rice Student" button sends the browser here, then on to Rice."""
    _require_rice_deployment()
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(32)
    resp = RedirectResponse(rice_authorization_url(state, nonce, code_verifier), status_code=status.HTTP_302_FOUND)
    resp.set_cookie(
        key=RICE_FLOW_COOKIE,
        value=create_rice_flow_token(state, nonce, code_verifier),
        max_age=RICE_FLOW_MINUTES * 60,
        path=_RICE_FLOW_COOKIE_PATH,
        httponly=True,
        secure=IS_PRODUCTION,
        samesite="lax",
    )
    return resp


@router.get("/auth/rice/callback")
async def rice_oidc_callback(
    background_tasks: BackgroundTasks,
    quantaid_rice_oidc: Annotated[str | None, Cookie()] = None,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    """
    Rice sends the browser back here after sign-in. Sets the quantaid_token cookie and sends the browser on into the
    app, or back to the login page with ?rice_error=failed|disabled|conflict. Rice's error_description is never shown.
    """
    _require_rice_deployment()
    try:
        if error:
            raise RiceSignInError("failed", f"Rice answered with error {error[:40]!r}")
        flow = decode_rice_flow_token(quantaid_rice_oidc) if quantaid_rice_oidc else None
        if flow is None:
            raise RiceSignInError("failed", "no valid sign-in flow cookie (missing, expired or tampered with)")
        # The state proves this callback answers the sign-in this browser started (CSRF)
        if not code or not state or not secrets.compare_digest(state.encode(), str(flow["state"]).encode()):
            raise RiceSignInError("failed", "code or state is missing, or state doesn't match")
        identity = await fetch_rice_identity(code, flow["code_verifier"], flow["nonce"])
        result = await resolve_or_create_rice_user(identity, db)
    except RiceSignInError as err:
        logger.info("Rice sign-in stopped with %r: %s", err.code, err)
        return _redirect_to_frontend(f"?rice_error={err.code}")

    logger.debug("Rice login for %s (%s)", result.email, result.message)
    if result.created:
        background_tasks.add_task(send_welcome_email, result.email, identity.name)
    # The same landing page Login.tsx picks after Google sign-in
    resp = _redirect_to_frontend("admin-dashboard" if result.is_admin else result.redirect_to)
    _set_auth_cookie(resp, create_access_token(result.email, result.login_id))
    return resp

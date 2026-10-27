import logging
import os
from typing import Literal

from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
FIRST_TIME_USER_EMAIL = os.getenv("FIRST_TIME_USER_EMAIL")
ADMIN_EMAILS = set(email.strip().lower() for email in os.getenv("ADMIN_EMAILS", "").split(",") if email.strip())

# ENVIRONMENT: "production" makes the auth cookie Secure; "development" turns on DEBUG logging.
# Anything else is a plain local setup.
ENVIRONMENT = os.getenv("ENVIRONMENT", "")
IS_PRODUCTION = ENVIRONMENT == "production"
LOG_LEVEL = logging.DEBUG if ENVIRONMENT == "development" else logging.INFO

# Render sets this to the deployed commit; CI's staging deploy jobs wait until /health reports it.
# Unset outside Render (local, self-host), so /health reports null there.
RENDER_GIT_COMMIT = os.getenv("RENDER_GIT_COMMIT")

# COOKIE_SAMESITE: "lax" (default) when the frontend and API share a site, like quantaid.org. "none" only for a
# cross-site frontend, like Vercel -> Render staging; browsers then require the Secure flag, so it needs production.
_cookie_samesite = os.getenv("COOKIE_SAMESITE", "lax").lower()
if _cookie_samesite not in ("lax", "none"):
    raise RuntimeError('COOKIE_SAMESITE environment variable must be "lax" or "none"')
if _cookie_samesite == "none" and not IS_PRODUCTION:
    raise RuntimeError("COOKIE_SAMESITE=none needs ENVIRONMENT=production, because browsers require Secure with it")
COOKIE_SAMESITE: Literal["lax", "none"] = "none" if _cookie_samesite == "none" else "lax"

# CORS: allowed origins for cross-origin requests
# Can be overridden via CORS_ORIGINS env var (comma-separated)
_default_origins = [
    "http://localhost:5173",
    "https://quantum-ai-ed-front-end-smoky.vercel.app",
]
_env_origins = os.getenv("CORS_ORIGINS", "")
CORS_ORIGINS = [o.strip() for o in _env_origins.split(",") if o.strip()] if _env_origins else _default_origins

# JWT authentication
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY environment variable must be set")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "10080"))

# IS_RICE_DEPLOYMENT: "true" for quantaid.rice.edu (Rice SSO only, Google sign-in turned off), "false" for
# quantaid.org (Google sign-in). No default, so a Rice deployment can't end up accepting Google sign-in by omission.
_is_rice_deployment = os.getenv("IS_RICE_DEPLOYMENT", "").lower()
if _is_rice_deployment not in ("true", "false"):
    raise RuntimeError('IS_RICE_DEPLOYMENT environment variable must be "true" or "false"')
IS_RICE_DEPLOYMENT = _is_rice_deployment == "true"

# Google sign-in only accepts access tokens issued to this OAuth client
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
if not IS_RICE_DEPLOYMENT and not GOOGLE_CLIENT_ID:
    raise RuntimeError("GOOGLE_CLIENT_ID environment variable must be set when IS_RICE_DEPLOYMENT is false")

# Rice University OIDC: set these to enable Rice SSO. Leave unset to disable.
RICE_OIDC_CLIENT_ID = os.getenv("RICE_OIDC_CLIENT_ID", "")
RICE_OIDC_CLIENT_SECRET = os.getenv("RICE_OIDC_CLIENT_SECRET", "")
RICE_OIDC_REDIRECT_URI = os.getenv("RICE_OIDC_REDIRECT_URI", "")

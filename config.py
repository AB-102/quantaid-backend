import logging
import os

from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
FIRST_TIME_USER_EMAIL = os.getenv("FIRST_TIME_USER_EMAIL")
ADMIN_EMAILS = set(email.strip().lower() for email in os.getenv("ADMIN_EMAILS", "").split(",") if email.strip())

# ENVIRONMENT: "production" makes the auth cookie Secure + SameSite=None (needed for cross-site
# deployments like Vercel -> Render); "development" turns on DEBUG logging. Anything else is a plain local setup.
ENVIRONMENT = os.getenv("ENVIRONMENT", "")
IS_PRODUCTION = ENVIRONMENT == "production"
LOG_LEVEL = logging.DEBUG if ENVIRONMENT == "development" else logging.INFO

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

# Rice University OIDC: set these to enable Rice SSO. Leave unset to disable.
RICE_OIDC_CLIENT_ID = os.getenv("RICE_OIDC_CLIENT_ID", "")
RICE_OIDC_CLIENT_SECRET = os.getenv("RICE_OIDC_CLIENT_SECRET", "")
RICE_OIDC_REDIRECT_URI = os.getenv("RICE_OIDC_REDIRECT_URI", "")

import os
from dotenv import load_dotenv

load_dotenv()

FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY") or os.urandom(24)
MONGODB_URI = os.getenv("MONGODB_URI")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
FIRST_TIME_USER_EMAIL = os.getenv("FIRST_TIME_USER_EMAIL")
ADMIN_EMAILS = set(
    email.strip().lower()
    for email in os.getenv("ADMIN_EMAILS", "").split(",")
    if email.strip()
)

# Session expiry: how long before an idle session expires (in minutes)
# Default 7 days (10080 minutes). Set SESSION_LIFETIME_MINUTES in .env to override.
SESSION_LIFETIME_MINUTES = int(os.getenv("SESSION_LIFETIME_MINUTES", "10080"))

# CORS: allowed origins for cross-origin requests
# Can be overridden via CORS_ORIGINS env var (comma-separated)
_default_origins = [
    "http://localhost:5173",
    "https://quantum-ai-ed-front-end-smoky.vercel.app",
]
_env_origins = os.getenv("CORS_ORIGINS", "")
CORS_ORIGINS = [o.strip() for o in _env_origins.split(",") if o.strip()] if _env_origins else _default_origins

# Frontend URL for password reset links
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# Redis: set REDIS_URL to connect. Leave unset for local dev (falls back to in-memory).
REDIS_URL = os.getenv("REDIS_URL", "")

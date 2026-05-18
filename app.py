import atexit
import logging
import os
from datetime import timedelta

from bson import ObjectId
from flask import Flask, Response, jsonify, session
from flask import request as flask_request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_session import Session  # type: ignore[attr-defined]

from config import CORS_ORIGINS, FLASK_SECRET_KEY, REDIS_URL, RICE_OIDC_CLIENT_ID, SESSION_LIFETIME_MINUTES
from database.mongo import db, fs, mongo_client
from database.redis_client import redis_client
from database.seeding import seed_if_empty
from models.user import User
from routes.admin_users import admin_users_bp
from routes.ai import ai_bp

# --- Import Blueprints ---
from routes.auth import auth_bp
from routes.content import content_bp
from routes.feedback import feedback_bp
from routes.progress import progress_bp
from routes.users import users_bp

app = Flask(__name__)

app.secret_key = FLASK_SECRET_KEY

flask_env = os.getenv("FLASK_ENV", "").lower()
is_production = flask_env == "production"

# SameSite=None + Secure=True for cross-site production (e.g., Vercel → backend)
# SameSite=Lax + Secure=False for same-site development (localhost:5173 → localhost:5000)
app.config["SESSION_COOKIE_SAMESITE"] = "None" if is_production else "Lax"
app.config["SESSION_COOKIE_SECURE"] = is_production
app.config["SESSION_COOKIE_HTTPONLY"] = True  # JS can't read the cookie
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=SESSION_LIFETIME_MINUTES)

# --- Server-side sessions (Redis when available, default filesystem otherwise) ---
if redis_client:
    app.config["SESSION_TYPE"] = "redis"
    app.config["SESSION_REDIS"] = redis_client
    logging.info("Using Redis-backed server-side sessions")
else:
    app.config["SESSION_TYPE"] = "filesystem"
    logging.info("Redis unavailable — using filesystem sessions (local dev)")
app.config["SESSION_PERMANENT"] = True
app.config["SESSION_USE_SIGNER"] = True  # sign the session ID cookie
app.config["SESSION_KEY_PREFIX"] = "quantaied:"
Session(app)

# --- CORS ---
CORS(
    app,
    origins=CORS_ORIGINS,
    supports_credentials=True,
    allow_headers=["Content-Type", "X-Requested-With"],
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)

# --- Flask-Login ---
login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(email: str) -> User | None:
    """
    Called on every request to restore the user from the session cookie.
    Validates login_id to support instant session invalidation.
    """
    user_doc = db.users.find_one({"user_id": email})
    if not user_doc:
        return None
    if user_doc.get("disabled", False):
        return None
    user = User(user_doc)
    # Validate login_id — if it doesn't match, the session is stale
    stored_login_id = session.get("login_id")
    if user.login_id and stored_login_id != user.login_id:
        return None
    return user


@login_manager.unauthorized_handler
def unauthorized():
    return jsonify({"error": "Authentication required."}), 401


# --- Session expiry ---
@app.before_request
def make_session_permanent():
    session.permanent = True


# --- Rate Limiting ---
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],  # No global limit — apply per-route
    storage_uri=REDIS_URL if redis_client else "memory://",
)

# Apply stricter limits to auth endpoints (exempt /auth/check — called frequently by SPA)
limiter.limit("5 per minute")(auth_bp)


@limiter.request_filter
def _exempt_auth_check():
    return flask_request.endpoint == "auth.check"


# --- Register Blueprints ---
app.register_blueprint(auth_bp)
app.register_blueprint(content_bp)
app.register_blueprint(ai_bp)
app.register_blueprint(users_bp)
app.register_blueprint(progress_bp)
app.register_blueprint(feedback_bp)
app.register_blueprint(admin_users_bp)

# Rice SSO (OIDC) — only registered when credentials are configured
if RICE_OIDC_CLIENT_ID:
    from routes.rice_auth import rice_auth_bp

    app.register_blueprint(rice_auth_bp)


# --- Auto-seed MongoDB on startup ---
try:
    seed_if_empty()
except Exception:
    logging.exception("Auto-seed failed — database may be unavailable at startup")


# --- Quiz buffer flush (Redis → MongoDB every 30s) ---
if redis_client:
    from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore[import-untyped]

    from routes.progress import flush_quiz_buffer

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(flush_quiz_buffer, "interval", seconds=30, id="flush_quiz_buffer")
    scheduler.start()
    atexit.register(flush_quiz_buffer)
    logging.info("Quiz buffer flush scheduler started (every 30s)")


# --- Shared routes ---


@app.route("/file/<file_id>", methods=["GET"])
def serve_file(file_id):
    """Serve public files from GridFS. Files tagged visibility='admin' are blocked."""
    try:
        file_obj = fs.get(ObjectId(file_id))
        # Only serve files explicitly tagged as public (or legacy files without a tag)
        visibility = getattr(file_obj, "visibility", "public") or "public"
        if visibility == "admin":
            return jsonify({"error": "File not found"}), 404
        return Response(
            file_obj.read(),
            mimetype=file_obj["contentType"] or "application/octet-stream",  # ty: ignore[not-subscriptable]
            headers={"Content-Disposition": f'inline; filename="{file_obj.filename}"'},
        )
    except Exception as e:
        print(f"Error serving file {file_id}: {e}")
        return jsonify({"error": "File not found"}), 404


@app.route("/ping", methods=["GET"])
def ping():
    try:
        mongo_client.admin.command("ping")
        db_status = "connected"
    except Exception:
        logging.exception("MongoDB ping failed")
        db_status = "error"
    return jsonify({"status": "pong", "database": db_status}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

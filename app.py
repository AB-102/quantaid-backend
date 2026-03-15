import os
from datetime import timedelta
from flask import Flask, jsonify, session, Response
from flask_cors import CORS
from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from bson import ObjectId
from config import FLASK_SECRET_KEY, CORS_ORIGINS, SESSION_LIFETIME_MINUTES
from database.mongo import mongo_client, db, fs
from models.user import User
import logging

# --- Import Blueprints ---
from routes.auth import auth_bp
from routes.content import content_bp
from routes.ai import ai_bp
from routes.users import users_bp
from routes.progress import progress_bp
from routes.feedback import feedback_bp
from routes.admin_users import admin_users_bp

app = Flask(__name__)

app.secret_key = FLASK_SECRET_KEY

flask_env = os.getenv("FLASK_ENV", "").lower()
default_secure = flask_env == "production"
session_cookie_secure_env = os.getenv("SESSION_COOKIE_SECURE")
if session_cookie_secure_env is not None:
    session_cookie_secure = session_cookie_secure_env.lower() in ("1", "true", "yes")
else:
    session_cookie_secure = default_secure

app.config['SESSION_COOKIE_SAMESITE'] = 'None'
app.config['SESSION_COOKIE_SECURE'] = session_cookie_secure
app.config['SESSION_COOKIE_HTTPONLY'] = True        # JS can't read the cookie
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=SESSION_LIFETIME_MINUTES)

# --- CORS ---
CORS(
    app,
    origins=CORS_ORIGINS,
    supports_credentials=True,
    allow_headers=["Content-Type", "X-Requested-With"],
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
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
    user_doc = db.users.find_one({'user_id': email})
    if not user_doc:
        return None
    if user_doc.get('disabled', False):
        return None
    user = User(user_doc)
    # Validate login_id — if it doesn't match, the session is stale
    stored_login_id = session.get('login_id')
    if user.login_id and stored_login_id != user.login_id:
        return None
    return user


@login_manager.unauthorized_handler
def unauthorized():
    return jsonify({'error': 'Authentication required.'}), 401


# --- Session expiry ---
@app.before_request
def make_session_permanent():
    session.permanent = True


# --- Rate Limiting ---
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],  # No global limit — apply per-route
    storage_uri="memory://",
)

# Apply stricter limits to auth endpoints
limiter.limit("5 per minute")(auth_bp)

# --- Register Blueprints ---
app.register_blueprint(auth_bp)
app.register_blueprint(content_bp)
app.register_blueprint(ai_bp)
app.register_blueprint(users_bp)
app.register_blueprint(progress_bp)
app.register_blueprint(feedback_bp)
app.register_blueprint(admin_users_bp)


# --- Shared routes ---

@app.route('/file/<file_id>', methods=['GET'])
def serve_file(file_id):
    """Serve public files from GridFS. Files tagged visibility='admin' are blocked."""
    try:
        file_obj = fs.get(ObjectId(file_id))
        # Only serve files explicitly tagged as public (or legacy files without a tag)
        visibility = getattr(file_obj, 'visibility', 'public') or 'public'
        if visibility == 'admin':
            return jsonify({'error': 'File not found'}), 404
        return Response(
            file_obj.read(),
            mimetype=file_obj.content_type or 'application/octet-stream',
            headers={
                'Content-Disposition': f'inline; filename="{file_obj.filename}"'
            }
        )
    except Exception as e:
        print(f"Error serving file {file_id}: {e}")
        return jsonify({'error': 'File not found'}), 404


@app.route('/ping', methods=['GET'])
def ping():
    try:
        mongo_client.admin.command('ping')
        db_status = "connected"
    except Exception as e:
        logging.exception("MongoDB ping failed")
        db_status = "error"
    return jsonify({'status': 'pong', 'database': db_status}), 200


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

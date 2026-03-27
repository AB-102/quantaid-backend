import re

from flask import Blueprint, jsonify, request, session
from flask_cors import cross_origin
from flask_login import current_user, login_user, logout_user

from config import ADMIN_EMAILS
from services.auth_service import (
    authenticate_user,
    create_email_user,
    create_password_reset_token,
    get_user_by_email,
    hash_password,
    reset_password_with_token,
    rotate_login_id,
    verify_password,
)
from services.email_service import send_password_reset_email

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@auth_bp.route("/signup", methods=["POST"])
@cross_origin(supports_credentials=True)
def signup():
    data = request.json or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password", "")
    name = (data.get("name") or "").strip()

    if not email or not EMAIL_REGEX.match(email):
        return jsonify({"error": "Valid email is required."}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400

    existing = get_user_by_email(email)
    if existing:
        # Return a conflict when the email is already registered.
        return jsonify({"error": "Invalid email or this account already exists."}), 409

    user = create_email_user(email, password, name)

    # Set admin flag
    if email in ADMIN_EMAILS:
        from database.mongo import db

        db.users.update_one({"user_id": email}, {"$set": {"is_admin": True}})
        user.is_admin = True

    # Log user in immediately
    login_user(user)
    session["login_id"] = user.login_id

    return jsonify(
        {
            "message": "Account created successfully.",
            "redirect_to": "profile-creation",
            "is_admin": user.is_admin,
        }
    ), 201


@auth_bp.route("/login", methods=["POST"])
@cross_origin(supports_credentials=True)
def login():
    data = request.json or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    user, error = authenticate_user(email, password)
    if not user:
        # Map specific authentication failures to appropriate HTTP status codes.
        # Default to 401 for generic authentication failures (e.g., bad credentials).
        status_code = 401
        if isinstance(error, str):
            lowered = error.lower()
            if "disabled" in lowered:
                # Account exists but is disabled -> forbidden.
                status_code = 403
            elif "lock" in lowered:
                # Account is locked / lockout condition -> locked.
                status_code = 423
        return jsonify({"error": error}), status_code

    # Refresh admin status from ADMIN_EMAILS (source of truth)
    is_admin = email in ADMIN_EMAILS
    if user.is_admin != is_admin:
        from database.mongo import db

        db.users.update_one({"user_id": email}, {"$set": {"is_admin": is_admin}})
        user.is_admin = is_admin

    login_user(user)
    session["login_id"] = user.login_id

    redirect_to = "map" if user.profile_complete else "profile-creation"

    return jsonify(
        {
            "message": "Login successful.",
            "redirect_to": redirect_to,
            "is_admin": user.is_admin,
        }
    ), 200


@auth_bp.route("/check", methods=["GET"])
@cross_origin(supports_credentials=True)
def check():
    """Check if the current session is valid. Called by frontend on mount."""
    if current_user.is_authenticated:
        return jsonify(
            {
                "authenticated": True,
                "email": current_user.email,
                "is_admin": current_user.is_admin,
            }
        ), 200
    return jsonify({"authenticated": False}), 200


@auth_bp.route("/forgot-password", methods=["POST"])
@cross_origin(supports_credentials=True)
def forgot_password():
    """
    Request a password reset email.
    Always returns success to prevent email enumeration.
    """
    data = request.json or {}
    email = (data.get("email") or "").strip().lower()

    if email and EMAIL_REGEX.match(email):
        token = create_password_reset_token(email)
        if token:
            send_password_reset_email(email, token)

    # Always return success regardless of whether email exists
    return jsonify({"message": "If an account with that email exists, a reset link has been sent."}), 200


@auth_bp.route("/reset-password", methods=["POST"])
@cross_origin(supports_credentials=True)
def reset_password():
    data = request.json or {}
    token = data.get("token", "")
    new_password = data.get("password", "")

    if not token:
        return jsonify({"error": "Reset token is required."}), 400
    if len(new_password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400

    success, error = reset_password_with_token(token, new_password)
    if not success:
        return jsonify({"error": error}), 400

    return jsonify({"message": "Password has been reset. You can now log in."}), 200


@auth_bp.route("/change-password", methods=["POST"])
@cross_origin(supports_credentials=True)
def change_password():
    """Change password for logged-in users who have email auth."""
    if not current_user.is_authenticated:
        return jsonify({"error": "Authentication required."}), 401

    data = request.json or {}
    current_password = data.get("current_password", "")
    new_password = data.get("new_password", "")

    if not current_user.has_password:
        # Google-only user setting a password for the first time
        if len(new_password) < 8:
            return jsonify({"error": "Password must be at least 8 characters."}), 400
        from database.mongo import db

        new_login_id = rotate_login_id(current_user.email)
        db.users.update_one({"user_id": current_user.email}, {"$set": {"password_hash": hash_password(new_password)}})
        session["login_id"] = new_login_id
        return jsonify({"message": "Password set successfully. You can now log in with email and password."}), 200

    # Existing password user — require current password
    if not current_password:
        return jsonify({"error": "Current password is required."}), 400
    if len(new_password) < 8:
        return jsonify({"error": "New password must be at least 8 characters."}), 400
    if not verify_password(current_password, current_user.password_hash):
        return jsonify({"error": "Current password is incorrect."}), 401

    from database.mongo import db

    new_login_id = rotate_login_id(current_user.email)
    db.users.update_one({"user_id": current_user.email}, {"$set": {"password_hash": hash_password(new_password)}})
    session["login_id"] = new_login_id
    return jsonify({"message": "Password changed successfully."}), 200


@auth_bp.route("/logout", methods=["POST"])
@cross_origin(supports_credentials=True)
def auth_logout():
    """Log out the current user (Flask-Login session)."""
    logout_user()
    session.clear()
    return jsonify({"message": "Logged out successfully."}), 200

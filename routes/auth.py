from flask import Blueprint, jsonify, session
from flask_cors import cross_origin
from flask_login import current_user, logout_user

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


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


@auth_bp.route("/logout", methods=["POST"])
@cross_origin(supports_credentials=True)
def auth_logout():
    """Log out the current user (Flask-Login session)."""
    logout_user()
    session.clear()
    return jsonify({"message": "Logged out successfully."}), 200

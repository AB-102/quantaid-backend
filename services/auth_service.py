import secrets

from database.mongo import db
from models.user import User


def generate_login_id() -> str:
    """Generate a cryptographically random login_id for session invalidation."""
    return secrets.token_hex(32)


def get_user_by_email(email: str) -> User | None:
    """Look up a user by email and return a User object, or None."""
    doc = db.users.find_one({"user_id": email.lower()})
    if doc:
        return User(doc)
    return None


def rotate_login_id(email: str) -> str:
    """
    Generate a new login_id and save it. Used on logout to invalidate all other sessions.
    Returns the new login_id.
    """
    new_login_id = generate_login_id()
    db.users.update_one({"user_id": email.lower()}, {"$set": {"login_id": new_login_id}})
    return new_login_id

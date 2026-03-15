import secrets
from datetime import datetime, timezone, timedelta
from passlib.hash import argon2
from database.mongo import db
from models.user import User
from pymongo import ReturnDocument

# Account lockout settings
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(minutes=15)


def hash_password(password: str) -> str:
    """Hash a password using Argon2id."""
    return argon2.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against an Argon2id hash."""
    try:
        return argon2.verify(password, password_hash)
    except Exception:
        return False


def generate_login_id() -> str:
    """Generate a cryptographically random login_id for session invalidation."""
    return secrets.token_hex(32)


def get_user_by_email(email: str) -> User | None:
    """Look up a user by email and return a User object, or None."""
    doc = db.users.find_one({'user_id': email.lower()})
    if doc:
        return User(doc)
    return None


def create_email_user(email: str, password: str, name: str = '') -> User:
    """
    Create a new user with email/password auth.
    Returns the User object.
    """
    login_id = generate_login_id()
    user_doc = {
        'user_id': email.lower(),
        'name': name,
        'picture': '',
        'google_sub': None,
        'password_hash': hash_password(password),
        'login_id': login_id,
        'is_admin': False,
        'profile_complete': False,
        'unlockedLevels': [0],
        'completedQuizzes': [],
        'hasViewedFirstLesson': False,
        'failed_login_attempts': 0,
        'locked_until': None,
        'createdAt': datetime.now(timezone.utc),
    }
    db.users.insert_one(user_doc)
    return User(user_doc)


def authenticate_user(email: str, password: str) -> tuple[User | None, str]:
    """
    Authenticate a user by email and password.
    Returns (user, error_message). user is None on failure.
    Handles account lockout and failed attempt tracking.
    """
    user = get_user_by_email(email)
    if not user:
        # Don't reveal whether email exists
        return None, 'Invalid email or password.'

    if not user.has_password:
        return None, 'This account uses Google sign-in. Please log in with Google.'

    # Check disabled
    doc = db.users.find_one({'user_id': email.lower()}, {'disabled': 1})
    if doc and doc.get('disabled', False):
        return None, 'This account has been disabled. Contact an administrator.'

    # Check account lockout
    if user.is_locked:
        locked = user.locked_until
        if locked.tzinfo is None:
            locked = locked.replace(tzinfo=timezone.utc)
        remaining = locked - datetime.now(timezone.utc)
        mins = max(1, int(remaining.total_seconds() / 60))
        return None, f'Account is locked. Try again in {mins} minute(s).'

    # Verify password
    if not verify_password(password, user.password_hash):
        _record_failed_attempt(email)
        return None, 'Invalid email or password.'

    # Success — reset failed attempts and rotate login_id
    new_login_id = generate_login_id()
    db.users.update_one(
        {'user_id': email.lower()},
        {'$set': {
            'failed_login_attempts': 0,
            'locked_until': None,
            'login_id': new_login_id,
            'lastLoginAt': datetime.now(timezone.utc),
        }}
    )
    # Refresh user object with new login_id
    user.login_id = new_login_id
    user.failed_login_attempts = 0
    user.locked_until = None
    return user, ''


def _record_failed_attempt(email: str):
    """Increment failed login attempts; lock account if threshold exceeded."""
    result = db.users.find_one_and_update(
        {'user_id': email.lower()},
        {'$inc': {'failed_login_attempts': 1}},
        return_document=ReturnDocument.AFTER,
    )
    if result and result.get('failed_login_attempts', 0) >= MAX_FAILED_ATTEMPTS:
        db.users.update_one(
            {'user_id': email.lower()},
            {'$set': {'locked_until': datetime.now(timezone.utc) + LOCKOUT_DURATION}}
        )


def rotate_login_id(email: str) -> str:
    """
    Generate a new login_id and save it. Used on password change
    or "log out all other sessions".
    Returns the new login_id.
    """
    new_login_id = generate_login_id()
    db.users.update_one(
        {'user_id': email.lower()},
        {'$set': {'login_id': new_login_id}}
    )
    return new_login_id


def create_password_reset_token(email: str) -> str | None:
    """
    Create a password reset token stored in the user document.
    Returns the token, or None if user not found / not email auth.
    """
    user = get_user_by_email(email)
    if not user or not user.has_password:
        return None

    token = secrets.token_urlsafe(32)
    db.users.update_one(
        {'user_id': email.lower()},
        {'$set': {
            'reset_token': token,
            'reset_token_expires': datetime.now(timezone.utc) + timedelta(hours=1),
        }}
    )
    return token


def reset_password_with_token(token: str, new_password: str) -> tuple[bool, str]:
    """
    Reset a user's password using a valid reset token.
    Returns (success, error_message).
    """
    user_doc = db.users.find_one({
        'reset_token': token,
        'reset_token_expires': {'$gt': datetime.now(timezone.utc)},
    })
    if not user_doc:
        return False, 'Invalid or expired reset link.'

    new_login_id = generate_login_id()
    db.users.update_one(
        {'user_id': user_doc['user_id']},
        {
            '$set': {
                'password_hash': hash_password(new_password),
                'login_id': new_login_id,
                'failed_login_attempts': 0,
                'locked_until': None,
            },
            '$unset': {
                'reset_token': '',
                'reset_token_expires': '',
            }
        }
    )
    return True, ''

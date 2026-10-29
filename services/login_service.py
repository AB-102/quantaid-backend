"""What every sign-in method shares: its result, and the fields a new account starts with."""

from datetime import UTC, datetime

from pydantic import BaseModel


class LoginResult(BaseModel):
    email: str
    login_id: str
    is_admin: bool
    redirect_to: str
    message: str
    created: bool = False


def new_user_doc(email: str, name: str | None, login_id: str, is_admin: bool) -> dict:
    """A new account. Each sign-in method adds its own fields, like google_sub or rice_sub."""
    return {
        "user_id": email,
        "name": name,
        "login_id": login_id,
        "is_admin": is_admin,
        "profile_complete": False,
        "completedQuizzes": [],
        "hasViewedFirstLesson": False,
        "createdAt": datetime.now(UTC),
    }


def is_disabled(user_doc: dict | None) -> bool:
    return bool(user_doc and user_doc.get("disabled", False))

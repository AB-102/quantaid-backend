from flask_login import UserMixin


class User(UserMixin):
    """
    Flask-Login user model backed by MongoDB.

    The only supported auth method is Google SSO (google_sub set).
    Rice OIDC will be a second method when implemented.

    The `login_id` field is a random token stored in both the DB and the session
    cookie. On every request, Flask-Login's user_loader checks that they match.
    Rotating login_id in the DB (e.g. on logout) instantly invalidates every
    other session for that user.
    """

    def __init__(self, user_doc: dict):
        self._doc = user_doc
        self.email = user_doc.get("user_id", "")  # user_id field is email
        self.name = user_doc.get("name", "")
        self.picture = user_doc.get("picture", "")
        self.is_admin = user_doc.get("is_admin", False)
        self.login_id = user_doc.get("login_id", "")
        self.google_sub = user_doc.get("google_sub") or ""
        self.profile_complete = user_doc.get("profile_complete", False)

    # Flask-Login requires get_id() — we return email (same as user_id in DB)
    def get_id(self):
        return self.email

    @property
    def has_google(self) -> bool:
        return bool(self.google_sub)

from flask_login import UserMixin


class User(UserMixin):
    """
    Flask-Login user model backed by MongoDB.

    Auth methods are derived from which fields are populated:
      - google_sub set   → can use Google SSO
      - password_hash set → can use email/password
      - both set         → linked account (both methods work)

    The `login_id` field is a random token stored in both the DB and the session
    cookie. On every request, Flask-Login's user_loader checks that they match.
    Changing login_id in the DB (e.g. on password change or "log out all devices")
    instantly invalidates every other session for that user.
    """

    def __init__(self, user_doc: dict):
        self._doc = user_doc
        self.email = user_doc.get('user_id', '')          # user_id field is email
        self.name = user_doc.get('name', '')
        self.picture = user_doc.get('picture', '')
        self.is_admin = user_doc.get('is_admin', False)
        self.login_id = user_doc.get('login_id', '')
        self.password_hash = user_doc.get('password_hash') or ''
        self.google_sub = user_doc.get('google_sub') or ''
        self.profile_complete = user_doc.get('profile_complete', False)
        self.failed_login_attempts = user_doc.get('failed_login_attempts', 0)
        self.locked_until = user_doc.get('locked_until', None)

    # Flask-Login requires get_id() — we return email (same as user_id in DB)
    def get_id(self):
        return self.email

    @property
    def has_google(self) -> bool:
        return bool(self.google_sub)

    @property
    def has_password(self) -> bool:
        return bool(self.password_hash)

    @property
    def auth_methods(self) -> list[str]:
        """Derive available auth methods from populated fields."""
        methods = []
        if self.has_google:
            methods.append('google')
        if self.has_password:
            methods.append('email')
        return methods

    @property
    def is_locked(self):
        """Check if account is currently locked out."""
        if self.locked_until is None:
            return False
        from datetime import datetime, timezone
        locked = self.locked_until
        # MongoDB may return naive datetimes (UTC without tzinfo)
        if locked.tzinfo is None:
            locked = locked.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) < locked

from datetime import UTC, datetime, timedelta

import jwt

from config import JWT_EXPIRE_MINUTES, JWT_SECRET_KEY

_ALGORITHM = "HS256"


def create_access_token(email: str, login_id: str) -> str:
    """Sign a token for the user. `lid` must match the user's current login_id for the token to be accepted."""
    expire = datetime.now(UTC) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    return jwt.encode({"sub": email, "lid": login_id, "exp": expire}, JWT_SECRET_KEY, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[_ALGORITHM])
    except jwt.PyJWTError:
        return None

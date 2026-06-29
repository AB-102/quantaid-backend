from datetime import UTC, datetime, timedelta

import jwt

from config import JWT_EXPIRE_MINUTES, JWT_SECRET_KEY

_ALGORITHM = "HS256"


def create_access_token(email: str, is_admin: bool) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    return jwt.encode({"sub": email, "is_admin": is_admin, "exp": expire}, JWT_SECRET_KEY, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[_ALGORITHM])
    except jwt.PyJWTError:
        return None

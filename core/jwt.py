from datetime import UTC, datetime, timedelta

import jwt

from config import JWT_EXPIRE_MINUTES, JWT_SECRET_KEY

_ALGORITHM = "HS256"

# Rice sign-in keeps its state, nonce and PKCE verifier in a short-lived cookie signed like the access token.
# Its audience means it can't be used as an access token: decode_access_token expects none and rejects it.
_RICE_FLOW_AUDIENCE = "rice-oidc-flow"
RICE_FLOW_MINUTES = 10


def create_access_token(email: str, login_id: str) -> str:
    """Sign a token for the user. `lid` must match the user's current login_id for the token to be accepted."""
    expire = datetime.now(UTC) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    return jwt.encode({"sub": email, "lid": login_id, "exp": expire}, JWT_SECRET_KEY, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[_ALGORITHM])
    except jwt.PyJWTError:
        return None


def create_rice_flow_token(state: str, nonce: str, code_verifier: str) -> str:
    """Sign what the Rice callback needs to check that it's answering this browser's sign-in."""
    expire = datetime.now(UTC) + timedelta(minutes=RICE_FLOW_MINUTES)
    claims = {"aud": _RICE_FLOW_AUDIENCE, "state": state, "nonce": nonce, "code_verifier": code_verifier, "exp": expire}
    return jwt.encode(claims, JWT_SECRET_KEY, algorithm=_ALGORITHM)


def decode_rice_flow_token(token: str) -> dict | None:
    """The flow token's claims, or None if it's invalid, expired or not a flow token."""
    try:
        return jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[_ALGORITHM],
            audience=_RICE_FLOW_AUDIENCE,
            options={"require": ["exp", "aud", "state", "nonce", "code_verifier"]},
        )
    except jwt.PyJWTError:
        return None

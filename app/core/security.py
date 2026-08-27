"""Password hashing and JWT helpers.

Two independent concerns live here:

1. Password hashing with bcrypt. We never store plaintext passwords; we store
   a bcrypt hash (which includes a per-password random salt). Verifying a login
   re-hashes the candidate password with the stored salt and compares.

2. Stateless JWT access tokens. On login we sign a token whose payload names the
   user (the "sub" claim) and an expiry. The server trusts a request because the
   signature verifies with our secret key, so no server-side session table is
   needed. The trade-off (documented in docs/authentication.md) is that a token
   cannot be revoked before it expires.
"""
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from app.core.config import settings

# bcrypt is deliberately slow, which is what makes brute-forcing stolen hashes hard.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Return a bcrypt hash of the given password."""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a plaintext password against a stored bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str | int, expires_minutes: int | None = None) -> str:
    """Create a signed JWT whose 'sub' claim identifies the user.

    `subject` is the user id. We stringify it because the JWT spec expects the
    subject to be a string.
    """
    expire_minutes = expires_minutes or settings.access_token_expire_minutes
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(subject),
        "iat": now,
        "exp": now + timedelta(minutes=expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Decode and verify a JWT. Raises jwt.PyJWTError on any problem
    (bad signature, expired, malformed). Callers translate that into a 401.
    """
    return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])

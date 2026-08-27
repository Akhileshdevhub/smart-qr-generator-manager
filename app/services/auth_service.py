"""User registration and login logic, kept out of the route handlers.

The route layer only does HTTP concerns (status codes, request parsing); the
actual rules — "email must be unique", "verify the password hash" — live here so
they can be unit-tested without spinning up the web server.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.db.models import User


class EmailAlreadyRegistered(Exception):
    """Raised when registering an email that already exists."""


class InvalidCredentials(Exception):
    """Raised when login email/password don't match."""


def register_user(db: Session, email: str, password: str, display_name: str = "") -> User:
    email = email.lower().strip()
    existing = db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise EmailAlreadyRegistered(email)

    user = User(
        email=email,
        password_hash=hash_password(password),  # store the hash, never the plaintext
        display_name=display_name or email.split("@")[0],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    email = email.lower().strip()
    user = db.scalar(select(User).where(User.email == email))
    # Verify the hash even if the user is missing? We short-circuit here for
    # simplicity. The same generic error is returned in both cases so an
    # attacker can't tell "wrong password" from "no such user".
    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentials()
    return user

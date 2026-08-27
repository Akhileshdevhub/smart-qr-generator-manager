"""Reusable FastAPI dependencies for auth and ownership.

`get_current_user` turns a Bearer token into a User (or 401).
`get_owned_project` loads a QR project AND checks the caller owns it, returning
404 for both "doesn't exist" and "belongs to someone else" so an attacker can't
tell the difference (prevents probing which ids exist).

Every protected route depends on these, so authorization is enforced in one
place on the server — never trusted from the frontend.
"""
import jwt
from fastapi import Depends, HTTPException, Path, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.database import get_db
from app.db.models import QRProject, User

# auto_error=False so we can raise our own 401 with a clean message.
bearer_scheme = HTTPBearer(auto_error=False)

_CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or not credentials.credentials:
        raise _CREDENTIALS_ERROR
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise _CREDENTIALS_ERROR

    user = db.get(User, user_id)
    if user is None:
        raise _CREDENTIALS_ERROR
    return user


def get_owned_project(
    qr_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QRProject:
    """Load a project by id and confirm the current user owns it.

    Returning 404 (not 403) for someone else's project is deliberate: it hides
    whether that id exists at all. This is the server-side ownership check that
    stops User A from reaching User B's QR by editing the id in the URL.
    """
    project = db.get(QRProject, qr_id)
    if project is None or project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QR project not found")
    return project

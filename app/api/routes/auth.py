"""Authentication routes: register, login, and the current-user profile."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.rate_limit import limiter
from app.core.security import create_access_token
from app.db.database import get_db
from app.db.models import User
from app.schemas.token import Token
from app.schemas.user import ProfileUpdate, UserCreate, UserLogin, UserOut
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def register(request: Request, payload: UserCreate, db: Session = Depends(get_db)):
    try:
        user = auth_service.register_user(
            db, payload.email, payload.password, payload.display_name
        )
    except auth_service.EmailAlreadyRegistered:
        # 409 Conflict is the right code for "this resource already exists".
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    return user


@router.post("/login", response_model=Token)
@limiter.limit("10/minute")
def login(request: Request, payload: UserLogin, db: Session = Depends(get_db)):
    try:
        user = auth_service.authenticate_user(db, payload.email, payload.password)
    except auth_service.InvalidCredentials:
        # Same generic message whether the email or the password was wrong.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    token = create_access_token(subject=user.id)
    return Token(access_token=token)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/me", response_model=UserOut)
def update_me(
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.display_name = payload.display_name
    db.commit()
    db.refresh(current_user)
    return current_user

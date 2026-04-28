from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from api.db import get_db
from api.deps import get_current_user
from api.models import AppUser, UserCredential
from api.schemas import LoginRequest, RegisterRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    existing = db.scalar(select(AppUser).where(func.lower(AppUser.email) == payload.email.lower()))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = AppUser(email=payload.email.lower(), full_name=payload.full_name, phone=payload.phone)
    db.add(user)
    db.flush()

    credential = UserCredential(user_id=user.id, password_hash=hash_password(payload.password))
    db.add(credential)
    db.commit()

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(AppUser).where(func.lower(AppUser.email) == payload.email.lower()))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    credential = db.get(UserCredential, user.id)
    if not credential or not verify_password(payload.password, credential.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
    )


@router.get("/me", response_model=UserResponse)
def me(current_user: AppUser = Depends(get_current_user)) -> AppUser:
    return current_user

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
import os

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from api.cache import CachePolicy, CacheScope, CachedAPIRoute, cache_response
from api.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from api.db import get_db
from api.deps import get_current_user
from api.models import AppUser, UserCredential
from api.models.password_reset import PasswordResetCode
from api.schemas import (
    EmailCheckRequest,
    EmailCheckResponse,
    LoginRequest,
    OneSignalSubscriptionUpdate,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from api.services.email_service import send_reset_code

router = APIRouter(prefix="/auth", tags=["auth"], route_class=CachedAPIRoute)

MAX_RESET_ATTEMPTS = 5
RESET_CODE_TTL_MINUTES = 10


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=8)


class MessageResponse(BaseModel):
    message: str


def hash_reset_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


@router.post("/check-email", response_model=EmailCheckResponse)
def check_email(payload: EmailCheckRequest, db: Session = Depends(get_db)) -> EmailCheckResponse:
    existing = db.scalar(select(AppUser.id).where(func.lower(AppUser.email) == payload.email.lower()))
    return EmailCheckResponse(exists=existing is not None)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    existing = db.scalar(select(AppUser).where(func.lower(AppUser.email) == payload.email.lower()))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = AppUser(
        email=payload.email.lower(),
        full_name=payload.full_name,
        phone=payload.phone,
        onesignal_subscription_id=payload.onesignal_subscription_id,
        avatar_url=payload.avatar_url,
        birth_date=payload.birth_date,
    )
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

    if payload.onesignal_subscription_id and user.onesignal_subscription_id != payload.onesignal_subscription_id:
        user.onesignal_subscription_id = payload.onesignal_subscription_id
        db.commit()

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
    )


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> MessageResponse:
    user = db.scalar(select(AppUser).where(func.lower(AppUser.email) == payload.email.lower()))

    if user:
        db.execute(delete(PasswordResetCode).where(PasswordResetCode.user_id == user.id))
        code = f"{secrets.randbelow(1_000_000):06d}"
        db.add(
            PasswordResetCode(
                user_id=user.id,
                code_hash=hash_reset_code(code),
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=RESET_CODE_TTL_MINUTES),
            )
        )
        db.commit()
        background_tasks.add_task(send_reset_code, user.email, code)

    return MessageResponse(message="ok")


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> MessageResponse:
    user = db.scalar(select(AppUser).where(func.lower(AppUser.email) == payload.email.lower()))
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code")

    record = db.scalar(
        select(PasswordResetCode)
        .where(PasswordResetCode.user_id == user.id)
        .order_by(PasswordResetCode.created_at.desc())
    )
    if not record or record.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code")

    if record.attempts >= MAX_RESET_ATTEMPTS:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many attempts")

    if not secrets.compare_digest(record.code_hash, hash_reset_code(payload.code)):
        record.attempts += 1
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code")

    new_hash = hash_password(payload.new_password)
    credential = db.get(UserCredential, user.id)
    if credential:
        credential.password_hash = new_hash
    else:
        db.add(UserCredential(user_id=user.id, password_hash=new_hash))

    db.delete(record)
    db.commit()
    return MessageResponse(message="ok")

class GoogleLoginRequest(BaseModel):
    id_token: str


@router.post("/google", response_model=TokenResponse)
def google_login(payload: GoogleLoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    client_id = os.environ.get("GOOGLE_WEB_CLIENT_ID")
    if not client_id:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Google login not configured")

    try:
        info = google_id_token.verify_oauth2_token(payload.id_token, google_requests.Request(), client_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google token")

    email = (info.get("email") or "").lower()
    if not email or not info.get("email_verified"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google token")

    user = db.scalar(select(AppUser).where(func.lower(AppUser.email) == email))
    if not user:
        user = AppUser(
            email=email,
            full_name=info.get("name"),
            avatar_url=info.get("picture"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.get("/me", response_model=UserResponse)
@cache_response(CachePolicy(key="auth:me", tags=("users",), scope=CacheScope.USER))
def me(current_user: AppUser = Depends(get_current_user)) -> AppUser:
    return current_user


@router.patch("/me/onesignal-subscription", response_model=UserResponse)
def update_my_onesignal_subscription(
    payload: OneSignalSubscriptionUpdate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
) -> AppUser:
    current_user.onesignal_subscription_id = payload.onesignal_subscription_id
    db.commit()
    db.refresh(current_user)
    return current_user
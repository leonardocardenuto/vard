import uuid

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.core.security import TokenError, decode_access_token
from api.db import get_db
from api.models import AppUser, WorkspaceMember

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(request: Request, db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> AppUser:
    try:
        payload = decode_access_token(token)
    except TokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    subject = payload.get("sub")
    if not subject:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token subject")

    user = db.get(AppUser, uuid.UUID(subject))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    restricted = db.scalar(select(WorkspaceMember.user_id).where(
        WorkspaceMember.user_id == user.id, WorkspaceMember.status == "active",
        WorkspaceMember.role == "elderly").limit(1)) is not None
    if restricted and not (
        request.url.path.startswith("/mobile-monitor/")
        or request.url.path in {"/auth/me", "/auth/me/password", "/auth/me/onesignal-subscription", "/encryption-keys/me", "/invites/accept"}
    ):
        raise HTTPException(403, "Este perfil tem acesso somente ao monitoramento do celular.")
    return user


def require_workspace_membership(workspace_id: uuid.UUID, user_id: uuid.UUID, db: Session, *, allow_elderly: bool = False) -> WorkspaceMember:
    membership = db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.status == "active",
        )
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not an active workspace member")
    if membership.role == "elderly" and not allow_elderly:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Este perfil tem acesso somente ao monitoramento do celular.")
    return membership

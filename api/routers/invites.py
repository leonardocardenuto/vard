import secrets
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.core.config import get_settings
from api.db import get_db
from api.deps import get_current_user, require_workspace_membership
from api.models import AppUser, Workspace, WorkspaceInvite, WorkspaceMember
from api.schemas import InviteAccept, InviteCreate, InviteResponse
from api.services.invites import InviteEmailError, send_workspace_invite_email

settings = get_settings()
router = APIRouter(prefix="/invites", tags=["invites"])


@router.get("", response_model=list[InviteResponse])
def list_invites(
    workspace_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
) -> list[WorkspaceInvite]:
    require_workspace_membership(workspace_id, current_user.id, db)
    return list(
        db.scalars(
            select(WorkspaceInvite)
            .where(WorkspaceInvite.workspace_id == workspace_id)
            .order_by(WorkspaceInvite.created_at.desc())
        ).all()
    )


@router.post("", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
def create_invite(
    payload: InviteCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
) -> WorkspaceInvite:
    member = require_workspace_membership(payload.workspace_id, current_user.id, db)
    if member.role not in {"owner", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner/admin can invite")

    workspace = db.get(Workspace, payload.workspace_id)
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    pending_same_email = db.scalar(
        select(WorkspaceInvite).where(
            WorkspaceInvite.workspace_id == payload.workspace_id,
            WorkspaceInvite.status == "pending",
            func.lower(WorkspaceInvite.email) == payload.email.lower(),
        )
    )
    if pending_same_email:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="There is already a pending invite for this email")

    token = secrets.token_urlsafe(42)
    invite = WorkspaceInvite(
        workspace_id=payload.workspace_id,
        email=payload.email.lower(),
        role=payload.role,
        invited_by_user_id=current_user.id,
        token=token,
        status="pending",
        expires_at=datetime.now(UTC) + timedelta(hours=payload.expires_in_hours),
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    invite_url = f"{settings.app_base_url}/invites/accept?token={quote(token)}"
    try:
        send_workspace_invite_email(invite.email, workspace.name, invite_url, payload.role)
    except InviteEmailError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    return invite


@router.get("/{invite_id}", response_model=InviteResponse)
def get_invite(
    invite_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
) -> WorkspaceInvite:
    invite = db.get(WorkspaceInvite, invite_id)
    if not invite:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")

    require_workspace_membership(invite.workspace_id, current_user.id, db)
    return invite


@router.post("/accept", response_model=InviteResponse)
def accept_invite(
    payload: InviteAccept,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
) -> WorkspaceInvite:
    invite = db.scalar(select(WorkspaceInvite).where(WorkspaceInvite.token == payload.token))
    if not invite:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite token not found")

    if invite.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Invite is not pending")
    if invite.expires_at < datetime.now(UTC):
        invite.status = "expired"
        db.commit()
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Invite expired")

    existing_member = db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == invite.workspace_id,
            WorkspaceMember.user_id == current_user.id,
        )
    )
    if not existing_member:
        db.add(
            WorkspaceMember(
                workspace_id=invite.workspace_id,
                user_id=current_user.id,
                role=invite.role,
                status="active",
                invited_by_user_id=invite.invited_by_user_id,
                joined_at=datetime.now(UTC),
            )
        )
    else:
        existing_member.status = "active"
        existing_member.role = invite.role
        existing_member.joined_at = datetime.now(UTC)

    invite.status = "accepted"
    invite.accepted_by_user_id = current_user.id
    invite.accepted_at = datetime.now(UTC)

    db.commit()
    db.refresh(invite)
    return invite


@router.post("/{invite_id}/revoke", response_model=InviteResponse)
def revoke_invite(
    invite_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
) -> WorkspaceInvite:
    invite = db.get(WorkspaceInvite, invite_id)
    if not invite:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")

    member = require_workspace_membership(invite.workspace_id, current_user.id, db)
    if member.role not in {"owner", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner/admin can revoke invite")

    if invite.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only pending invites can be revoked")

    invite.status = "revoked"
    invite.revoked_at = datetime.now(UTC)
    db.commit()
    db.refresh(invite)
    return invite

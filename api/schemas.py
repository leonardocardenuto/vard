import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = None
    phone: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserBase(BaseModel):
    email: EmailStr
    full_name: str | None = None
    phone: str | None = None


class UserUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9-]+$")
    timezone: str = "UTC"


class WorkspaceUpdate(BaseModel):
    name: str | None = None
    timezone: str | None = None


class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    timezone: str
    created_by_user_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class CameraCreate(BaseModel):
    workspace_id: uuid.UUID
    name: str
    external_id: str | None = None
    connection_type: str = "rtsp"
    stream_url: str
    status: str = "offline"
    is_active: bool = True
    metadata: dict = Field(default_factory=dict)


class CameraUpdate(BaseModel):
    name: str | None = None
    external_id: str | None = None
    connection_type: str | None = None
    stream_url: str | None = None
    status: str | None = None
    is_active: bool | None = None
    metadata: dict | None = None


class CameraResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    external_id: str | None
    connection_type: str
    stream_url: str
    status: str
    is_active: bool
    metadata: dict = Field(alias="metadata_json")
    created_by_user_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class InviteCreate(BaseModel):
    workspace_id: uuid.UUID
    email: EmailStr
    role: str = Field(pattern=r"^(owner|admin|member|caregiver|viewer)$")
    expires_in_hours: int = Field(default=72, ge=1, le=720)


class InviteAccept(BaseModel):
    token: str


class InviteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    email: EmailStr
    role: str
    status: str
    expires_at: datetime
    invited_by_user_id: uuid.UUID | None
    accepted_by_user_id: uuid.UUID | None
    accepted_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class NotificationCreate(BaseModel):
    workspace_id: uuid.UUID
    camera_id: uuid.UUID | None = None
    notification_type: str
    severity: str = Field(pattern=r"^(low|medium|high|critical)$")
    title: str
    body: str
    payload: dict = Field(default_factory=dict)
    created_by: str = "system"


class NotificationUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
    severity: str | None = Field(default=None, pattern=r"^(low|medium|high|critical)$")
    payload: dict | None = None


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    camera_id: uuid.UUID | None
    notification_type: str
    severity: str
    title: str
    body: str
    payload: dict
    created_by: str
    created_at: datetime

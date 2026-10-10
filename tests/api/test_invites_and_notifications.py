import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.models import Notification, WorkspaceInvite, WorkspaceMember
from tests.api.helpers import auth_headers, create_workspace, register_user


def test_invite_can_only_be_accepted_by_recipient(client, db_session: Session):
    owner_token = register_user(client, "invite-owner@example.com")
    recipient_token = register_user(client, "invite-recipient@example.com")
    stranger_token = register_user(client, "invite-stranger@example.com")
    workspace = create_workspace(client, owner_token, slug="invite-home")

    created = client.post(
        "/invites",
        headers=auth_headers(owner_token),
        json={
            "workspace_id": workspace["id"],
            "email": "invite-recipient@example.com",
            "role": "caregiver",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["token"]
    invite = db_session.get(WorkspaceInvite, uuid.UUID(created.json()["id"]))
    assert invite is not None
    assert created.json()["token"] == invite.token

    duplicate = client.post(
        "/invites",
        headers=auth_headers(owner_token),
        json={
            "workspace_id": workspace["id"],
            "email": "INVITE-RECIPIENT@example.com",
            "role": "viewer",
        },
    )
    assert duplicate.status_code == 409

    denied = client.post(
        "/invites/accept",
        headers=auth_headers(stranger_token),
        json={"token": invite.token},
    )
    assert denied.status_code == 403

    accepted = client.post(
        "/invites/accept",
        headers=auth_headers(recipient_token),
        json={"token": invite.token},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "accepted"

    recipient_id = uuid.UUID(
        client.get("/auth/me", headers=auth_headers(recipient_token)).json()["id"]
    )
    membership = db_session.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == uuid.UUID(workspace["id"]),
            WorkspaceMember.user_id == recipient_id,
        )
    )
    assert membership is not None
    assert membership.role == "caregiver"
    assert membership.status == "active"


def test_notification_creation_lists_for_members_and_persists(client, db_session: Session, monkeypatch):
    pushed = []
    monkeypatch.setattr(
        "api.routers.notifications.send_push_to_subscription_ids",
        lambda subscription_ids, **payload: pushed.append((subscription_ids, payload)),
    )

    owner_token = register_user(client, "notification-owner@example.com")
    workspace = create_workspace(client, owner_token, slug="notification-home")

    created = client.post(
        "/notifications",
        headers=auth_headers(owner_token),
        json={
            "workspace_id": workspace["id"],
            "notification_type": "fall_detected",
            "severity": "critical",
            "title": "Queda detectada",
            "body": "Movimento compatível com queda.",
            "payload": {"confidence": 0.96},
        },
    )
    assert created.status_code == 201, created.text
    notification_id = uuid.UUID(created.json()["id"])

    persisted = db_session.get(Notification, notification_id)
    assert persisted is not None
    assert persisted.payload == {"confidence": 0.96}
    assert pushed and pushed[0][1]["title"] == "Queda detectada"

    listed = client.get(
        "/notifications",
        params={"workspace_id": workspace["id"]},
        headers=auth_headers(owner_token),
    )
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [str(notification_id)]

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.models import Camera, Notification, Workspace, WorkspaceMember
from tests.api.helpers import auth_headers, create_workspace, register_user


def test_deleting_workspace_cascades_related_database_rows(client, db_session: Session):
    owner_token = register_user(client, "cascade-owner@example.com")
    workspace = create_workspace(client, owner_token, slug="cascade-home")
    workspace_id = uuid.UUID(workspace["id"])

    camera_response = client.post(
        "/cameras",
        headers=auth_headers(owner_token),
        json={
            "workspace_id": workspace["id"],
            "name": "Corredor",
            "stream_url": "rtsp://camera.test/corridor",
        },
    )
    assert camera_response.status_code == 201, camera_response.text

    notification_response = client.post(
        "/notifications",
        headers=auth_headers(owner_token),
        json={
            "workspace_id": workspace["id"],
            "camera_id": camera_response.json()["id"],
            "notification_type": "fall_detected",
            "severity": "high",
            "title": "Alerta",
            "body": "Teste de integridade",
        },
    )
    assert notification_response.status_code == 201, notification_response.text

    deleted = client.delete(
        f"/workspaces/{workspace['id']}", headers=auth_headers(owner_token)
    )
    assert deleted.status_code == 204

    assert db_session.get(Workspace, workspace_id) is None
    assert db_session.scalar(
        select(func.count()).select_from(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id
        )
    ) == 0
    assert db_session.scalar(
        select(func.count()).select_from(Camera).where(Camera.workspace_id == workspace_id)
    ) == 0
    assert db_session.scalar(
        select(func.count()).select_from(Notification).where(
            Notification.workspace_id == workspace_id
        )
    ) == 0

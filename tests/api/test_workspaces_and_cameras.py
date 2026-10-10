import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.models import AppUser, Camera, WorkspaceMember
from api.services.camera_discovery import DetectedCameraConnection
from tests.api.helpers import auth_headers, create_workspace, register_user


def _user_id(client, token: str) -> uuid.UUID:
    response = client.get("/auth/me", headers=auth_headers(token))
    assert response.status_code == 200
    return uuid.UUID(response.json()["id"])


def test_workspace_creation_creates_owner_membership_and_isolates_access(client, db_session: Session):
    owner_token = register_user(client, "workspace-owner@example.com")
    outsider_token = register_user(client, "workspace-outsider@example.com")
    workspace = create_workspace(client, owner_token)

    membership = db_session.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == uuid.UUID(workspace["id"]),
            WorkspaceMember.user_id == _user_id(client, owner_token),
        )
    )
    assert membership is not None
    assert membership.role == "owner"
    assert membership.status == "active"

    owner_list = client.get("/workspaces", headers=auth_headers(owner_token))
    assert owner_list.status_code == 200
    assert [item["id"] for item in owner_list.json()] == [workspace["id"]]

    denied = client.get(
        f"/workspaces/{workspace['id']}", headers=auth_headers(outsider_token)
    )
    assert denied.status_code == 403

    duplicate = client.post(
        "/workspaces",
        headers=auth_headers(owner_token),
        json={"name": "Outra casa", "slug": workspace["slug"]},
    )
    assert duplicate.status_code == 409


def test_camera_permissions_and_crud_persist_in_database(client, db_session: Session):
    owner_token = register_user(client, "camera-owner@example.com")
    viewer_token = register_user(client, "camera-viewer@example.com")
    workspace = create_workspace(client, owner_token, slug="camera-home")
    workspace_id = uuid.UUID(workspace["id"])

    db_session.add(
        WorkspaceMember(
            workspace_id=workspace_id,
            user_id=_user_id(client, viewer_token),
            role="viewer",
            status="active",
            invited_by_user_id=_user_id(client, owner_token),
        )
    )
    db_session.commit()

    created = client.post(
        "/cameras",
        headers=auth_headers(owner_token),
        json={
            "workspace_id": workspace["id"],
            "name": "Sala",
            "connection_type": "rtsp",
            "stream_url": "rtsp://camera.test/live",
            "metadata": {"position": "ceiling"},
        },
    )
    assert created.status_code == 201, created.text
    camera = created.json()
    assert camera["metadata"] == {"position": "ceiling"}

    persisted = db_session.get(Camera, uuid.UUID(camera["id"]))
    assert persisted is not None
    assert persisted.metadata_json == {"position": "ceiling"}

    visible = client.get(
        "/cameras",
        params={"workspace_id": workspace["id"]},
        headers=auth_headers(viewer_token),
    )
    assert visible.status_code == 200
    assert [item["id"] for item in visible.json()] == [camera["id"]]

    forbidden_create = client.post(
        "/cameras",
        headers=auth_headers(viewer_token),
        json={
            "workspace_id": workspace["id"],
            "name": "Quarto",
            "stream_url": "rtsp://camera.test/bedroom",
        },
    )
    assert forbidden_create.status_code == 403

    forbidden_delete = client.delete(
        f"/cameras/{camera['id']}", headers=auth_headers(viewer_token)
    )
    assert forbidden_delete.status_code == 403

    updated = client.patch(
        f"/cameras/{camera['id']}",
        headers=auth_headers(owner_token),
        json={"name": "Sala principal", "status": "online"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Sala principal"
    assert updated.json()["status"] == "online"

    deleted = client.delete(
        f"/cameras/{camera['id']}", headers=auth_headers(owner_token)
    )
    assert deleted.status_code == 204
    assert db_session.get(Camera, uuid.UUID(camera["id"])) is None


def test_camera_auto_configuration_detects_and_persists_connection(client, monkeypatch):
    owner_token = register_user(client, "camera-auto-owner@example.com")
    workspace = create_workspace(client, owner_token, slug="camera-auto-home")
    detected_url = "rtsp://camera-user:camera-pass@192.168.1.25/stream1"

    monkeypatch.setattr(
        "api.routers.cameras.detect_camera_connection",
        lambda host, username, password: DetectedCameraConnection(
            connection_type="rtsp",
            protocol="rtsp-auto",
            stream_url=detected_url,
        ),
    )

    response = client.post(
        "/cameras/auto-configure",
        headers=auth_headers(owner_token),
        json={
            "workspace_id": workspace["id"],
            "host": "192.168.1.25",
            "username": "camera-user",
            "password": "camera-pass",
        },
    )

    assert response.status_code == 201, response.text
    camera = response.json()
    assert camera["name"] == "Câmera 192.168.1.25"
    assert camera["connection_type"] == "rtsp"
    assert camera["stream_url"] == detected_url
    assert camera["status"] == "online"
    assert camera["metadata"] == {
        "host": "192.168.1.25",
        "location": "192.168.1.25",
        "protocol": "rtsp-auto",
        "username": "camera-user",
    }

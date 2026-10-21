import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from api.models import AppUser, MobileMonitorDevice, Notification, WorkspaceMember, PushDelivery
from tests.api.helpers import auth_headers, create_workspace, register_user


def setup_elderly(client):
    owner = register_user(client, "mobile-owner@example.com")
    elderly = register_user(client, "mobile-elder@example.com", full_name="Teste Idoso")
    workspace = create_workspace(client, owner, slug="mobile-monitor")
    invite = client.post("/invites", headers=auth_headers(owner), json={
        "workspace_id": workspace["id"], "email": "mobile-elder@example.com", "role": "elderly",
    })
    assert invite.status_code == 201, invite.text
    accepted = client.post("/invites/accept", headers=auth_headers(elderly), json={"token": invite.json()["token"]})
    assert accepted.status_code == 200, accepted.text
    return owner, elderly, workspace


def test_invite_restricts_elderly_and_monitor_registration(client):
    owner, elderly, workspace = setup_elderly(client)
    profile = client.get("/mobile-monitor/profile", headers=auth_headers(elderly))
    assert profile.json() == {"restricted": True, "workspaces": [{"id": workspace["id"], "name": workspace["name"]}]}
    assert client.get("/mobile-monitor/profile", headers=auth_headers(owner)).json()["restricted"] is False
    for path in (f'/cameras?workspace_id={workspace["id"]}',
                 f'/notifications?workspace_id={workspace["id"]}',
                 f'/camera-streams/{uuid.uuid4()}/mjpeg', "/workspaces"):
        assert client.get(path, headers=auth_headers(elderly)).status_code == 403, path
    denied = client.post("/mobile-monitor/devices", headers=auth_headers(owner), json={"workspace_id": workspace["id"]})
    assert denied.status_code == 403
    assert client.post("/workspaces", headers=auth_headers(elderly), json={"name": "No", "slug": "not-allowed"}).status_code == 403


def test_reports_idempotently_without_login_token_and_revokes(client, db_session, monkeypatch):
    pushed = []
    monkeypatch.setattr("api.routers.mobile_monitor.enqueue_notification_push", lambda db, notification: pushed.append(notification))
    owner, elderly, workspace = setup_elderly(client)
    registered = client.post("/mobile-monitor/devices", headers=auth_headers(elderly), json={"workspace_id": workspace["id"]})
    assert registered.status_code == 200, registered.text
    device = registered.json()
    headers = auth_headers(device["device_token"])
    stored = db_session.get(MobileMonitorDevice, uuid.UUID(device["device_id"]))
    assert stored.token_hash != device["device_token"]
    assert client.get("/auth/me", headers=headers).status_code == 401
    assert client.get("/mobile-monitor/devices/current", headers=headers).status_code == 200
    payload = {"event_id": str(uuid.uuid4()), "occurred_at": datetime.now(UTC).isoformat(), "peak_g": 3.2}
    for _ in range(2):
        response = client.post("/mobile-monitor/falls", headers=headers, json=payload)
        assert response.status_code == 200, response.text
    assert len(pushed) == 1
    notification = db_session.get(Notification, uuid.UUID(payload["event_id"]))
    assert str(notification.workspace_id) == workspace["id"]
    assert notification.camera_id is None
    assert notification.payload["source"] == "accelerometer"
    assert client.get(f'/notifications?workspace_id={workspace["id"]}', headers=auth_headers(owner)).json()[0]["id"] == payload["event_id"]
    assert client.delete("/mobile-monitor/devices/current", headers=headers).status_code == 204
    assert client.post("/mobile-monitor/falls", headers=headers, json=payload).status_code == 401


def test_role_removal_invalidates_device_and_foreign_workspace_cannot_register(client, db_session):
    owner, elderly, workspace = setup_elderly(client)
    foreign = create_workspace(client, owner, name="Outro", slug="other-monitor")
    assert client.post("/mobile-monitor/devices", headers=auth_headers(elderly), json={"workspace_id": foreign["id"]}).status_code == 403
    registered = client.post("/mobile-monitor/devices", headers=auth_headers(elderly), json={"workspace_id": workspace["id"]}).json()
    member = db_session.scalar(select(WorkspaceMember).where(
        WorkspaceMember.role == "elderly", WorkspaceMember.workspace_id == uuid.UUID(workspace["id"])))
    member.status = "removed"
    db_session.commit()
    headers = auth_headers(registered["device_token"])
    assert client.get("/mobile-monitor/devices/current", headers=headers).status_code == 403
    assert client.post("/mobile-monitor/falls", headers=headers, json={
        "event_id": str(uuid.uuid4()), "occurred_at": datetime.now(UTC).isoformat(), "peak_g": 3,
    }).status_code == 403


def test_same_device_can_send_multiple_distinct_falls(client, db_session, monkeypatch):
    pushed = []
    monkeypatch.setattr("api.routers.mobile_monitor.enqueue_notification_push",
                        lambda db, notification: pushed.append(notification))
    _, elderly, workspace = setup_elderly(client)
    device = client.post("/mobile-monitor/devices", headers=auth_headers(elderly),
                         json={"workspace_id": workspace["id"]}).json()
    headers = auth_headers(device["device_token"])
    for _ in range(3):
        payload = {"event_id": str(uuid.uuid4()), "occurred_at": datetime.now(UTC).isoformat(), "peak_g": 3.2}
        for _ in range(2):
            response = client.post("/mobile-monitor/falls", headers=headers, json=payload)
            assert response.status_code == 200, response.text
            assert response.json()["notification_id"] == payload["event_id"]
        assert db_session.get(Notification, uuid.UUID(payload["event_id"])) is not None
        assert client.get("/mobile-monitor/devices/current", headers=headers).status_code == 200
    assert len(pushed) == 3


def test_fall_push_excludes_elderly_and_shared_phone_subscriptions(client, db_session, monkeypatch):
    from api.core.config import get_settings
    monkeypatch.setattr(get_settings(), "push_provider", "onesignal")
    owner, elderly, workspace = setup_elderly(client)
    elder_user = db_session.scalar(select(AppUser).where(AppUser.email == "mobile-elder@example.com"))
    owner_user = db_session.scalar(select(AppUser).where(AppUser.email == "mobile-owner@example.com"))
    elder_user.onesignal_subscription_id = "shared-phone"
    owner_user.onesignal_subscription_id = "shared-phone"
    register_user(client, "mobile-recipient@example.com")
    recipient = db_session.scalar(select(AppUser).where(AppUser.email == "mobile-recipient@example.com"))
    recipient.onesignal_subscription_id = "family-phone"
    db_session.add(WorkspaceMember(workspace_id=uuid.UUID(workspace["id"]),
                                   user_id=recipient.id, role="member", status="active"))
    db_session.commit()
    device = client.post("/mobile-monitor/devices", headers=auth_headers(elderly),
                         json={"workspace_id": workspace["id"]}).json()
    response = client.post("/mobile-monitor/falls", headers=auth_headers(device["device_token"]), json={
        "event_id": str(uuid.uuid4()), "occurred_at": datetime.now(UTC).isoformat(), "peak_g": 3,
    })
    assert response.status_code == 200, response.text
    assert [item.token for item in db_session.scalars(select(PushDelivery)).all()] == ["family-phone"]

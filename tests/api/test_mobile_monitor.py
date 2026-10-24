import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from api.models import AppUser, MobileMonitorDevice, Notification, WorkspaceMember
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
    monkeypatch.setattr("api.routers.mobile_monitor.send_push_to_subscription_ids", lambda ids, **data: pushed.append(data))
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
    assert "coordinates" not in notification.payload
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
    monkeypatch.setattr("api.routers.mobile_monitor.send_push_to_subscription_ids",
                        lambda ids, **data: pushed.append(data))
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
    pushed = []
    monkeypatch.setattr("api.routers.mobile_monitor.send_push_to_subscription_ids",
                        lambda ids, **data: pushed.append(ids))
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
    assert pushed == [["family-phone"]]


def test_mobile_fall_location_is_persisted_visible_and_preserved_on_retry(client, db_session, monkeypatch):
    monkeypatch.setattr("api.routers.mobile_monitor.send_push_to_subscription_ids", lambda *args, **kwargs: None)
    owner, elderly, workspace = setup_elderly(client)
    device = client.post("/mobile-monitor/devices", headers=auth_headers(elderly),
                         json={"workspace_id": workspace["id"]}).json()
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    coordinates = {"latitude": -23.55052, "longitude": -46.633308, "accuracy_m": 12.5, "captured_at": now,
                   "address": "Praça da Sé, Sé, São Paulo - SP, Brasil"}
    payload = {"event_id": str(uuid.uuid4()), "occurred_at": now, "peak_g": 3.2, "coordinates": coordinates}
    headers = auth_headers(device["device_token"])
    assert client.post("/mobile-monitor/falls", headers=headers, json=payload).status_code == 200
    # A later retry must not replace the original fall location.
    payload["coordinates"] = {**coordinates, "latitude": 0}
    assert client.post("/mobile-monitor/falls", headers=headers, json=payload).status_code == 200
    notification = db_session.get(Notification, uuid.UUID(payload["event_id"]))
    assert notification.payload["location"] == coordinates["address"]
    assert notification.payload["coordinates"] == coordinates
    visible = client.get(f'/notifications?workspace_id={workspace["id"]}', headers=auth_headers(owner))
    assert visible.json()[0]["payload"]["coordinates"] == coordinates
    assert client.get(f'/notifications/{payload["event_id"]}', headers=auth_headers(elderly)).status_code == 403


def test_invalid_mobile_location_is_rejected_without_saving_alert(client, db_session):
    _, elderly, workspace = setup_elderly(client)
    device = client.post("/mobile-monitor/devices", headers=auth_headers(elderly),
                         json={"workspace_id": workspace["id"]}).json()
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    coordinates = {"latitude": 0, "longitude": 0, "accuracy_m": 1, "captured_at": now}
    invalid = [{"latitude": 91}, {"longitude": -181}, {"accuracy_m": -1},
               {"captured_at": "2020-01-01T00:00:00Z"}, {"captured_at": "2026-01-01T00:00:00"}]
    for changes in invalid:
        payload = {"event_id": str(uuid.uuid4()), "occurred_at": now, "peak_g": 3.2,
                   "coordinates": {**coordinates, **changes}}
        response = client.post("/mobile-monitor/falls", headers=auth_headers(device["device_token"]), json=payload)
        assert response.status_code == 422, response.text
        assert db_session.get(Notification, uuid.UUID(payload["event_id"])) is None


def test_coordinate_only_mobile_fall_remains_compatible(client, db_session, monkeypatch):
    monkeypatch.setattr("api.routers.mobile_monitor.send_push_to_subscription_ids", lambda *args, **kwargs: None)
    _, elderly, workspace = setup_elderly(client)
    device = client.post("/mobile-monitor/devices", headers=auth_headers(elderly),
                         json={"workspace_id": workspace["id"]}).json()
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    coordinates = {"latitude": 0, "longitude": 0, "accuracy_m": 5, "captured_at": now}
    event_id = str(uuid.uuid4())
    response = client.post("/mobile-monitor/falls", headers=auth_headers(device["device_token"]), json={
        "event_id": event_id, "occurred_at": now, "peak_g": 3.2, "coordinates": coordinates,
    })
    assert response.status_code == 200, response.text
    notification = db_session.get(Notification, uuid.UUID(event_id))
    assert notification.payload["location"] == "Celular"
    assert notification.payload["coordinates"] == coordinates


def test_configuration_is_read_from_database_each_activation(client, db_session):
    from api.models import MobileMonitorSettings
    _, elderly, workspace = setup_elderly(client)
    def activate():
        device = client.post('/mobile-monitor/devices', headers=auth_headers(elderly),
                             json={'workspace_id': workspace['id']}).json()
        return client.get('/mobile-monitor/configuration', headers=auth_headers(device['device_token']))
    response = activate()
    assert response.status_code == 200, response.text
    assert response.json()['impact_g'] == 2.5
    stored = db_session.get(MobileMonitorSettings, 1)
    stored.parameters = {**stored.parameters, 'impact_g': 3.5, 'confirmation_timeout_ms': 30000}
    db_session.commit()
    response = activate()
    assert response.status_code == 200, response.text
    assert response.json()['impact_g'] == 3.5
    assert response.json()['confirmation_timeout_ms'] == 30000
    assert client.get('/mobile-monitor/configuration').status_code == 422
    assert client.get('/mobile-monitor/configuration', headers=auth_headers('invalid')).status_code == 401


def test_invalid_database_parameters_do_not_activate_protection(client, db_session):
    from api.models import MobileMonitorSettings
    _, elderly, workspace = setup_elderly(client)
    device = client.post('/mobile-monitor/devices', headers=auth_headers(elderly),
                         json={'workspace_id': workspace['id']}).json()
    headers = auth_headers(device['device_token'])
    assert client.get('/mobile-monitor/configuration', headers=headers).status_code == 200
    stored = db_session.get(MobileMonitorSettings, 1)
    stored.parameters = {**stored.parameters, 'stillness_duration_ms': 9000}
    db_session.commit()
    assert client.get('/mobile-monitor/configuration', headers=headers).status_code == 503
    assert client.delete('/mobile-monitor/devices/current', headers=headers).status_code == 204
    assert client.get('/mobile-monitor/configuration', headers=headers).status_code == 401


def test_settings_migration_seeds_defaults_and_preserves_custom_values(db_session):
    from pathlib import Path
    from sqlalchemy import text
    from api.mobile_monitor_config import MobileMonitorConfig
    from api.models import MobileMonitorSettings
    sql = (Path(__file__).resolve().parents[2] / 'sql/014_mobile_monitor_settings.sql').read_text()
    db_session.execute(text(sql))
    stored = db_session.get(MobileMonitorSettings, 1, populate_existing=True)
    assert stored.parameters == MobileMonitorConfig().model_dump()
    stored.parameters = {**stored.parameters, 'impact_g': 3.5}
    db_session.flush()
    db_session.execute(text(sql))
    assert db_session.get(MobileMonitorSettings, 1, populate_existing=True).parameters['impact_g'] == 3.5

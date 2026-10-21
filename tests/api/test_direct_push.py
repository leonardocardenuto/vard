import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from api.core.config import get_settings
from api.models import AppUser, Notification, PushDevice, PushDelivery, WorkspaceMember
from api.services.push import enqueue_notification_push, process_one
from api.services.push_providers import PushError
from tests.api.helpers import auth_headers, create_workspace, register_user


def setup_device(client, provider='fcm', email='push-owner@example.com', installation=None, token=None):
    auth = register_user(client, email)
    installation = installation or str(uuid.uuid4())
    registered = client.post('/push/devices', headers=auth_headers(auth), json={
        'installation_id': installation, 'provider': provider, 'token': token or f'{provider}-device-token',
    })
    assert registered.status_code == 200, registered.text
    return auth, installation, registered.json()['id']


@pytest.mark.parametrize('provider', ['fcm', 'onesignal'])
def test_both_providers_self_test_ack_and_access_control(client, db_session, monkeypatch, provider):
    auth, installation, device_id = setup_device(client, provider)
    other = register_user(client, 'push-other@example.com')
    sent = []
    monkeypatch.setattr('api.services.push.send_push', lambda *args, **kwargs: sent.append((args, kwargs)) or 'accepted-id')
    response = client.post('/push/test', headers=auth_headers(auth), json={'provider': provider, 'installation_id': installation})
    assert response.status_code == 202, response.text
    delivery_id = response.json()['delivery_id']
    assert db_session.scalar(select(func.count()).select_from(Notification)) == 0
    assert process_one(db_session)
    db_session.commit()
    assert sent[0][0][0] == provider
    assert sent[0][1]['delivery_id'] == delivery_id
    status = client.get(f'/push/deliveries/{delivery_id}', headers=auth_headers(auth)).json()
    assert status['status'] == 'accepted' and status['received_at'] is None
    assert status['send_started_at'] <= status['accepted_at']
    assert status['timing_ms']['provider_request'] >= 0
    assert status['timing_ms']['confirmation'] is None
    assert client.get(f'/push/deliveries/{delivery_id}', headers=auth_headers(other)).status_code == 404
    assert client.post(f'/push/deliveries/{delivery_id}/received', headers=auth_headers(other)).status_code == 404
    for _ in range(2):
        assert client.post(f'/push/deliveries/{delivery_id}/received', headers=auth_headers(auth),
                           json={'source': 'foreground'}).status_code == 204
    confirmed = client.get(f'/push/deliveries/{delivery_id}', headers=auth_headers(auth)).json()
    assert confirmed['status'] == 'received'
    assert confirmed['receipt_source'] == 'foreground'
    assert confirmed['timing_ms']['confirmation'] >= 0
    assert confirmed['timing_ms']['send_to_confirmation'] >= 0
    assert client.post(f'/push/deliveries/{delivery_id}/received', headers=auth_headers(auth),
                       json={'source': 'tap'}).status_code == 204
    assert client.get(f'/push/deliveries/{delivery_id}', headers=auth_headers(auth)).json()['received_at'] == confirmed['received_at']
    assert not process_one(db_session)
    assert len(sent) == 1


def test_transient_failure_retries_and_permanent_invalid_token_stops(client, db_session, monkeypatch):
    auth, installation, device_id = setup_device(client)
    created = client.post('/push/test', headers=auth_headers(auth), json={'provider': 'fcm', 'installation_id': installation}).json()
    def fail(*args, **kwargs):
        raise PushError('FCM_HTTP_503', retryable=True)
    monkeypatch.setattr('api.services.push.send_push', fail)
    assert process_one(db_session)
    db_session.commit()
    delivery = db_session.get(PushDelivery, uuid.UUID(created['delivery_id']))
    assert delivery.status == 'pending' and delivery.attempts == 1
    assert delivery.next_attempt_at > datetime.now(UTC)
    assert not process_one(db_session)
    delivery.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()
    def invalid(*args, **kwargs):
        raise PushError('FCM_HTTP_404', invalid_token=True)
    monkeypatch.setattr('api.services.push.send_push', invalid)
    assert process_one(db_session)
    db_session.commit()
    assert delivery.status == 'failed' and delivery.attempts == 2
    assert not db_session.get(PushDevice, uuid.UUID(device_id)).is_active


def test_logout_cancels_pending_push(client, db_session, monkeypatch):
    auth, installation, device_id = setup_device(client)
    result = client.post('/push/test', headers=auth_headers(auth), json={'provider': 'fcm', 'installation_id': installation}).json()
    assert client.delete(f'/push/devices/{installation}', headers=auth_headers(auth)).status_code == 204
    monkeypatch.setattr('api.services.push.send_push', lambda *args, **kwargs: pytest.fail('Revoked device must not receive'))
    assert process_one(db_session)
    assert db_session.get(PushDelivery, uuid.UUID(result['delivery_id'])).status == 'cancelled'


def test_token_transfer_between_accounts_cancels_previous_users_pending_push(client, db_session, monkeypatch):
    auth, installation, device_id = setup_device(client)
    result = client.post('/push/test', headers=auth_headers(auth), json={'provider': 'fcm', 'installation_id': installation}).json()
    other = register_user(client, 'push-next@example.com')
    for _ in range(2):
        registered = client.post('/push/devices', headers=auth_headers(other), json={
            'provider': 'fcm', 'installation_id': installation, 'token': 'fcm-device-token',
        })
        assert registered.status_code == 200
    assert db_session.scalar(select(func.count()).select_from(PushDevice)) == 1
    monkeypatch.setattr('api.services.push.send_push', lambda *args, **kwargs: pytest.fail('Previous account must not receive'))
    assert process_one(db_session)
    assert db_session.get(PushDelivery, uuid.UUID(result['delivery_id'])).status == 'cancelled'


def test_notification_enqueues_atomically_and_idempotently_for_selected_provider(client, db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), 'push_provider', 'fcm')
    auth, installation, device_id = setup_device(client)
    workspace = create_workspace(client, auth, slug='push-events')
    response = client.post('/notifications', headers=auth_headers(auth), json={
        'workspace_id': workspace['id'], 'notification_type': 'fall_detected', 'severity': 'critical',
        'title': 'Teste evento', 'body': 'Teste', 'payload': {},
    })
    assert response.status_code == 201, response.text
    event = db_session.get(Notification, uuid.UUID(response.json()['id']))
    enqueue_notification_push(db_session, event)
    db_session.commit()
    deliveries = list(db_session.scalars(select(PushDelivery)).all())
    assert len(deliveries) == 1 and deliveries[0].provider == 'fcm'
    assert deliveries[0].notification_id == event.id
    owner_id = db_session.get(PushDevice, uuid.UUID(device_id)).user_id
    member = db_session.get(WorkspaceMember, (uuid.UUID(workspace['id']), owner_id))
    member.status = 'removed'
    db_session.commit()
    monkeypatch.setattr('api.services.push.send_push', lambda *args, **kwargs: pytest.fail('Removed member must not receive'))
    assert process_one(db_session)
    assert deliveries[0].status == 'cancelled'


def test_test_endpoint_is_self_only_and_rate_limited(client):
    auth, installation, device_id = setup_device(client)
    other = register_user(client, 'push-stranger@example.com')
    payload = {'provider': 'fcm', 'installation_id': installation}
    assert client.post('/push/test', headers=auth_headers(other), json=payload).status_code == 409
    for _ in range(5):
        assert client.post('/push/test', headers=auth_headers(auth), json=payload).status_code == 202
    assert client.post('/push/test', headers=auth_headers(auth), json=payload).status_code == 429


def test_benchmark_uses_identical_visible_payload_for_both_providers(client, db_session):
    auth, installation, _ = setup_device(client)
    response = client.post('/push/devices', headers=auth_headers(auth), json={
        'installation_id': installation, 'provider': 'onesignal', 'token': 'onesignal-benchmark-token',
    })
    assert response.status_code == 200
    for provider in ('onesignal', 'fcm'):
        response = client.post('/push/test', headers=auth_headers(auth), json={
            'provider': provider, 'installation_id': installation, 'benchmark': True,
        })
        assert response.status_code == 202
    deliveries = list(db_session.scalars(select(PushDelivery)).all())
    assert len(deliveries) == 2
    assert len({(d.title, d.body) for d in deliveries}) == 1
    assert deliveries[0].title == 'VARD · Teste de latência'

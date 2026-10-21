import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import requests

from api.services.push_providers import PushError, send_push


def response(status=200, **data):
    return SimpleNamespace(status_code=status, json=lambda: data)


@patch('api.services.push_providers.fcm_authorization', return_value=('test-project', 'oauth-secret'))
@patch('api.services.push_providers.post_push')
def test_fcm_http_v1_without_calling_onesignal(post, auth):
    post.return_value = response(name='projects/test-project/messages/123')
    result = send_push('fcm', 'native-token', title='Teste', body='Direto',
                       data={'notification_id': 'n1'}, delivery_id='delivery-id')
    assert result.endswith('/123')
    assert post.call_args.args[0] == 'https://fcm.googleapis.com/v1/projects/test-project/messages:send'
    message = post.call_args.kwargs['json']['message']
    assert message['token'] == 'native-token'
    assert message['android']['priority'] == 'high'
    assert message['data']['push_delivery_id'] == 'delivery-id'
    assert json.loads(message['data']['body'])['push_provider'] == 'fcm'
    assert 'onesignal' not in post.call_args.args[0]


@patch('api.services.push_providers.get_settings', return_value=SimpleNamespace(onesignal_app_id='app', onesignal_api_key='key'))
@patch('api.services.push_providers.post_push')
def test_onesignal_acceptance_idempotency(post, settings):
    post.return_value = response(id='message-id')
    assert send_push('onesignal', 'subscription', title='T', body='B', data={}, delivery_id='delivery-id') == 'message-id'
    assert post.call_args.kwargs['json']['idempotency_key'] == 'delivery-id'
    post.return_value = response(errors=['No recipients'])
    with pytest.raises(PushError, match='NOT_ACCEPTED'):
        send_push('onesignal', 'subscription', title='T', body='B', data={}, delivery_id='delivery-id')


@pytest.mark.parametrize('status,code,retryable,invalid', [(429, None, True, False), (503, None, True, False), (403, None, False, False), (404, 'UNREGISTERED', False, True)])
@patch('api.services.push_providers.fcm_authorization', return_value=('project', 'token'))
@patch('api.services.push_providers.post_push')
def test_provider_error_classification(post, auth, status, code, retryable, invalid):
    post.return_value = response(status, error={'details': [{'errorCode': code}]})
    with pytest.raises(PushError) as error:
        send_push('fcm', 'device-token', title='T', body='B', data={}, delivery_id='id')
    assert error.value.retryable is retryable
    assert error.value.invalid_token is invalid
    assert 'device-token' not in str(error.value)


@patch('api.services.push_providers.fcm_authorization', return_value=('project', 'token'))
@patch('api.services.push_providers.post_push', side_effect=requests.Timeout('secret-url'))
def test_transport_errors_do_not_expose_secrets(post, auth):
    with pytest.raises(PushError, match='NETWORK_ERROR') as error:
        send_push('fcm', 'device-token', title='T', body='B', data={}, delivery_id='id')
    assert error.value.retryable
    assert 'secret' not in str(error.value)


def test_http_connections_are_reused_per_thread_and_closed(monkeypatch):
    import threading
    from unittest.mock import MagicMock
    from api.services import push_providers as providers
    monkeypatch.setattr(providers, '_transport', threading.local())
    created = []
    def new_session():
        session = MagicMock()
        created.append(session)
        return session
    monkeypatch.setattr(providers.requests, 'Session', new_session)
    first = providers.http_session()
    assert providers.http_session() is first
    def other_thread():
        assert providers.http_session() is not first
        providers.close_push_transport()
    thread = threading.Thread(target=other_thread)
    thread.start()
    thread.join()
    providers.close_push_transport()
    assert len(created) == 2
    for session in created:
        session.close.assert_called_once()

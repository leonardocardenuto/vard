"""Direct FCM HTTP v1 and optional OneSignal transport. Never log credentials/tokens."""
import json
import threading
from pathlib import Path

import requests
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import service_account

from api.core.config import get_settings


class PushError(Exception):
    def __init__(self, code: str, *, retryable: bool = False, invalid_token: bool = False):
        super().__init__(code)
        self.retryable = retryable
        self.invalid_token = invalid_token


_credentials = None
_credentials_path = None
_lock = threading.Lock()
_transport = threading.local()


def http_session():
    # One session per worker thread: reuse TLS/TCP without sharing mutable sessions.
    if not hasattr(_transport, "session"):
        _transport.session = requests.Session()
    return _transport.session


def close_push_transport():
    session = getattr(_transport, "session", None)
    if session is not None:
        session.close()
        del _transport.session


def post_push(*args, **kwargs):
    return http_session().post(*args, **kwargs)


def fcm_authorization():
    global _credentials, _credentials_path
    path = get_settings().fcm_service_account_file
    if not path or not Path(path).is_file():
        raise PushError("FCM_CREDENTIALS_MISSING")
    with _lock:
        try:
            if _credentials is None or _credentials_path != path:
                _credentials = service_account.Credentials.from_service_account_file(
                    path, scopes=["https://www.googleapis.com/auth/firebase.messaging"])
                _credentials_path = path
            if not _credentials.valid:
                _credentials.refresh(GoogleRequest(session=http_session()))
            return _credentials.project_id, _credentials.token
        except Exception:
            raise PushError("FCM_AUTH_FAILED", retryable=True) from None


def send_push(provider: str, token: str, *, title: str, body: str, data: dict, delivery_id: str) -> str:
    settings = get_settings()
    safe_data = {**data, "push_delivery_id": delivery_id, "push_provider": provider}
    if provider == "fcm":
        project, access_token = fcm_authorization()
        url = f"https://fcm.googleapis.com/v1/projects/{project}/messages:send"
        headers = {"Authorization": f"Bearer {access_token}"}
        payload = {"message": {
            "token": token,
            "notification": {"title": title, "body": body},
            "data": {**{k: str(v) for k, v in safe_data.items()}, "body": json.dumps(safe_data)},
            "android": {"priority": "high", "ttl": "3600s", "notification": {
                "channel_id": "vard-alerts", "tag": str(data.get("notification_id", delivery_id)),
            }},
        }}
    elif provider == "onesignal":
        if not settings.onesignal_app_id or not settings.onesignal_api_key:
            raise PushError("ONESIGNAL_CREDENTIALS_MISSING")
        url = "https://api.onesignal.com/notifications"
        headers = {"Authorization": f"Key {settings.onesignal_api_key}"}
        payload = {"app_id": settings.onesignal_app_id, "target_channel": "push",
                   "include_subscription_ids": [token], "headings": {"en": title},
                   "contents": {"en": body}, "data": safe_data,
                   "idempotency_key": delivery_id, "ttl": 3600}
    else:
        raise PushError("UNKNOWN_PROVIDER")
    try:
        response = post_push(url, json=payload, headers=headers, timeout=10)
    except requests.RequestException:
        raise PushError("NETWORK_ERROR", retryable=True) from None
    try:
        result = response.json()
    except ValueError:
        result = {}
    if response.status_code >= 400:
        codes = [item.get("errorCode") for item in result.get("error", {}).get("details", []) if isinstance(item, dict)]
        raise PushError(f"{provider.upper()}_HTTP_{response.status_code}",
                        retryable=response.status_code in {408, 429} or response.status_code >= 500,
                        invalid_token=provider == "fcm" and "UNREGISTERED" in codes)
    message_id = result.get("name") if provider == "fcm" else result.get("id")
    if not message_id:
        # OneSignal may return HTTP 200 with errors/no valid subscriptions.
        raise PushError(f"{provider.upper()}_NOT_ACCEPTED")
    return str(message_id)

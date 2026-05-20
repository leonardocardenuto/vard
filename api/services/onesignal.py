import json
import logging
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from api.core.config import get_settings

logger = logging.getLogger(__name__)


def send_push_to_subscription_ids(
    subscription_ids: list[str],
    *,
    title: str,
    body: str,
    data: dict | None = None,
) -> None:
    settings = get_settings()
    if not settings.onesignal_app_id or not settings.onesignal_api_key:
        logger.info(
            "Skipping OneSignal push because ONESIGNAL_APP_ID or ONESIGNAL_API_KEY is not configured"
        )
        return

    if not subscription_ids:
        return

    payload = {
        "app_id": settings.onesignal_app_id,
        "target_channel": "push",
        "include_subscription_ids": subscription_ids[:20000],
        "headings": {"en": title},
        "contents": {"en": body},
        "custom_data": data or {},
    }
    request = Request(
        "https://api.onesignal.com/notifications",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Key {settings.onesignal_api_key}",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=10) as response:
            response.read()
    except HTTPError as exc:
        logger.warning(
            "OneSignal push failed with HTTP %s: %s",
            exc.code,
            exc.read().decode("utf-8", errors="replace"),
        )
    except URLError as exc:
        logger.warning("OneSignal push failed: %s", exc.reason)

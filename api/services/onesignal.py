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
    external_user_ids: list[str] | None = None,
) -> None:
    settings = get_settings()
    if not settings.onesignal_app_id or not settings.onesignal_api_key:
        logger.info(
            "Skipping OneSignal push because ONESIGNAL_APP_ID or ONESIGNAL_API_KEY is not configured"
        )
        return

    user_ids = list(dict.fromkeys(external_user_ids or []))
    if not subscription_ids and not user_ids:
        return

    payload = {
        "app_id": settings.onesignal_app_id,
        "target_channel": "push",
        "headings": {"en": title},
        "contents": {"en": body},
        "data": data or {},
    }
    # login(user.id) links every device to the same OneSignal user. A single
    # stored subscription can be replaced by a later login on an emulator.
    if user_ids:
        payload["include_aliases"] = {"external_id": user_ids[:20000]}
    else:
        payload["include_subscription_ids"] = list(dict.fromkeys(subscription_ids))[:20000]
    if (data or {}).get("notification_type") == "fall_detected":
        payload["existing_android_channel_id"] = "vard-fall-sound-v1"
        payload["android_sound"] = "vard_fall_alert"  # Android < 8; newer versions use the channel.
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
            result = json.loads(response.read())
            if result.get("errors"):
                logger.warning("OneSignal did not accept all push recipients: %s", result["errors"])
            logger.info("OneSignal push request accepted: notification_id=%s targets=%s",
                        result.get("id"), len(user_ids or subscription_ids))
    except HTTPError as exc:
        logger.warning(
            "OneSignal push failed with HTTP %s: %s",
            exc.code,
            exc.read().decode("utf-8", errors="replace"),
        )
    except (URLError, TimeoutError, OSError) as exc:
        logger.warning("OneSignal push failed: %s", exc)

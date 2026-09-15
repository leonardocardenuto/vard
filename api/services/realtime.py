from __future__ import annotations

import json
import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)

CHANNEL_PREFIX = "vard:notifications:workspace:"
_publisher: Any = None


def workspace_channel(workspace_id: uuid.UUID) -> str:
    return f"{CHANNEL_PREFIX}{workspace_id}"


def _get_publisher() -> Any:
    global _publisher
    if _publisher is not None:
        return _publisher

    from api.core.config import get_settings

    settings = get_settings()
    if not settings.redis_url:
        return None

    try:
        from redis import Redis

        client = Redis.from_url(settings.redis_url, decode_responses=True)
        client.ping()
        _publisher = client
        return client
    except Exception:
        logger.warning("realtime: Redis unavailable, real-time publishing disabled")
        return None


def publish_notification_created(workspace_id: uuid.UUID, notification: dict[str, Any]) -> None:
    client = _get_publisher()
    if client is None:
        return

    try:
        message = json.dumps(
            {
                "event": "notification.created",
                "workspace_id": str(workspace_id),
                "notification": notification,
            }
        )
        client.publish(workspace_channel(workspace_id), message)
    except Exception:
        logger.warning("realtime: failed to publish notification.created", exc_info=True)
        global _publisher
        _publisher = None

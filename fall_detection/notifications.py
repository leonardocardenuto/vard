from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class NotificationConfig:
    endpoint: str
    token: str
    workspace_id: str
    camera_id: str | None = None
    created_by: str = "system"
    title: str = "Queda detectada"
    body: str = "Uma possivel queda foi detectada pela camera."
    timeout_seconds: float = 10.0


class NotificationSender:
    def __init__(self, config: NotificationConfig, logger: logging.Logger | None = None):
        self.config = config
        self.logger = logger or logging.getLogger(__name__)

    def send_fall_detected(self, payload: dict[str, Any]) -> bool:
        body = {
            "workspace_id": self.config.workspace_id,
            "camera_id": self.config.camera_id,
            "notification_type": "fall_detected",
            "severity": "critical",
            "title": self.config.title,
            "body": self.config.body,
            "payload": payload,
            "created_by": self.config.created_by,
        }
        data = json.dumps(body).encode("utf-8")
        request = Request(
            self.config.endpoint,
            data=data,
            headers={
                "Authorization": f"Bearer {self.config.token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.config.timeout_seconds) as response:
                status_code = getattr(response, "status", response.getcode())
                if 200 <= int(status_code) < 300:
                    return True
                self.logger.error("Falha ao criar notificacao de queda. status=%s", status_code)
                return False
        except HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="replace")
            self.logger.error(
                "Falha HTTP ao criar notificacao de queda. status=%s body=%s",
                exc.code,
                response_body,
            )
        except URLError as exc:
            self.logger.error("Falha de conexao ao criar notificacao de queda: %s", exc.reason)
        except Exception:
            self.logger.exception("Erro inesperado ao criar notificacao de queda.")
        return False
